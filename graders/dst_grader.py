"""graders/dst_grader.py
Three-tier deterministic grader for OrderBook-DST tasks.
See docs/07_GRADER_SPEC.md and docs/05_INVARIANTS_AND_DATA.md section 4.
"""
import importlib
import json
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore

from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.invariants import check_invariants
from exchange_core.types import BasketLeg, Event
from graders.hidden_seeds import get_task_seeds
from graders.import_policy import check_candidate_target_files
from graders.sandbox import prepare_overlay
from graders.trace_gen import generate_trace, make_noisy_fix_trace

REPO_ROOT = Path(__file__).resolve().parent.parent


def _event_from_dict(d: dict[str, Any]) -> Event:
    d_copy = dict(d)
    if isinstance(d_copy.get("body"), dict):
        d_copy["body"] = _event_from_dict(d_copy["body"])
    if isinstance(d_copy.get("legs"), (list, tuple)):
        d_copy["legs"] = tuple(
            BasketLeg(**leg) if isinstance(leg, dict) else leg for leg in d_copy["legs"]
        )
    return Event(**d_copy)


@dataclass
class FailureDetail:
    seed: int
    event_index: int
    invariant: str
    plain_name: str
    message: str
    diff: dict[str, Any]


@dataclass
class ScoreRecord:
    task_id: str
    t1: float
    t2: float
    t3: float
    score: float
    passed: bool
    first_failure: Optional[dict[str, Any]] = None
    coverage: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def _load_task_metadata(task_id: str) -> dict[str, Any]:
    task_toml = REPO_ROOT / "tasks" / task_id / "task.toml"
    if not task_toml.exists():
        raise FileNotFoundError(f"task.toml not found for {task_id}")
    return tomli.loads(task_toml.read_text(encoding="utf-8"))


def grade_tier1(
    task_id: str,
    overlay_dir: Path,
    timeout_s: int = 60,
) -> tuple[float, Optional[str]]:
    """Run public tests in workspace via sandboxed subprocess (Rule docs/07)."""
    public_tests_dir = REPO_ROOT / "tasks" / task_id / "public_tests"
    if not public_tests_dir.exists():
        return 1.0, None

    target_test_dir = overlay_dir / "tests"
    if target_test_dir.exists():
        shutil.rmtree(target_test_dir)
    shutil.copytree(public_tests_dir, target_test_dir)

    runner_code = f"""
import sys
import json
sys.path.insert(0, r"{overlay_dir}")
import pytest

class ResultCollector:
    def __init__(self):
        self.passed = 0
        self.total = 0

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            self.total += 1
            if report.passed:
                self.passed += 1

collector = ResultCollector()
pytest.main(["-q", str(r"{target_test_dir}")], plugins=[collector])
score = (collector.passed / collector.total) if collector.total > 0 else 0.0
print(json.dumps({{"passed": collector.passed, "total": collector.total, "score": score}}))
"""
    from graders.sandbox import run_sandboxed

    cmd = [sys.executable, "-I", "-c", runner_code]
    code, stdout, stderr = run_sandboxed(cmd, cwd=overlay_dir, timeout_s=timeout_s)

    for line in reversed(stdout.splitlines()):
        try:
            res = json.loads(line)
            if "score" in res:
                return float(res["score"]), None
        except Exception:
            continue

    if code != 0:
        return 0.0, f"Pytest exit {code}: {stderr or stdout}"

    return 0.0, f"Invalid runner output: {stdout} | {stderr}"


def _reports_equal(r1: list[Any], r2: list[Any]) -> bool:
    if len(r1) != len(r2):
        return False
    return all(getattr(a, "__dict__", a) == getattr(b, "__dict__", b) for a, b in zip(r1, r2))


def grade_tier2(
    task_id: str,
    cand_engine_cls: type,
    meta: dict[str, Any],
) -> tuple[float, Optional[str]]:
    """Run Tier 2 targeted trace with checkpoints and return fraction passed."""
    t2_file = REPO_ROOT / "tasks" / task_id / "tier2_trace.json"
    cfg = EngineConfig()

    if t2_file.exists():
        data = json.loads(t2_file.read_text(encoding="utf-8"))
        checkpoints = data.get("checkpoints", [])
        events_raw = data.get("events", [])
        accounts = data.get("accounts", {})
        mark_price = data.get("mark_price", 100_000_000)

        cand = cand_engine_cls(cfg, accounts, mark_price)
        passed_chk = 0
        chk_by_idx = {chk["event_index"]: chk for chk in checkpoints}

        for idx, ev_dict in enumerate(events_raw):
            ev = _event_from_dict(ev_dict)
            try:
                cand_reports = cand.process(ev)
            except Exception as e:
                return 0.0, f"Exception at event {idx}: {e}"

            if idx in chk_by_idx:
                chk = chk_by_idx[idx]
                chk_ok = True

                if "expected_reports" in chk:
                    c_idx = 0
                    for exp_r in chk["expected_reports"]:
                        matched = False
                        while c_idx < len(cand_reports):
                            cr = cand_reports[c_idx]
                            c_idx += 1
                            if cr.kind == exp_r.get("kind"):
                                fields_match = True
                                for k, v in exp_r.items():
                                    if getattr(cr, k, None) != v:
                                        fields_match = False
                                        break
                                if fields_match:
                                    matched = True
                                    break
                        if not matched:
                            chk_ok = False
                            break

                if chk_ok and "expected_accounts" in chk:
                    for acc_id, exp_acc in chk["expected_accounts"].items():
                        act_acc = cand.state.accounts.get(acc_id)
                        if not act_acc:
                            chk_ok = False
                            break
                        for k, v in exp_acc.items():
                            if getattr(act_acc, k, None) != v:
                                chk_ok = False
                                break

                if chk_ok and "expected_orders" in chk:
                    for oid_str, exp_ord in chk["expected_orders"].items():
                        oid = int(oid_str)
                        act_ord = cand.state.orders.get(oid)
                        if not act_ord:
                            chk_ok = False
                            break
                        for k, v in exp_ord.items():
                            if getattr(act_ord, k, None) != v:
                                chk_ok = False
                                break

                if chk_ok:
                    passed_chk += 1

        total_chk = len(checkpoints)
        return (passed_chk / total_chk if total_chk > 0 else 1.0), None

    # Fallback to deterministic trace of 40 events with 5 checkpoints
    trace = generate_trace(seed=999, profile=meta.get("profile", "replace_heavy"), num_events=40)
    ref = Engine(cfg, trace.accounts, trace.mark_price)
    cand = cand_engine_cls(cfg, trace.accounts, trace.mark_price)

    passed_chk = 0
    total_chk = 5
    chk_indices = [7, 15, 23, 31, 39]

    for idx, event in enumerate(trace.events):
        r_ref = ref.process(event)
        try:
            r_cand = cand.process(event)
        except Exception as e:
            return 0.0, f"Exception at event {idx}: {e}"

        if idx in chk_indices:
            if _reports_equal(r_ref, r_cand):
                passed_chk += 1

    return (passed_chk / total_chk), None


def grade_tier3(
    task_id: str,
    cand_engine_cls: type,
    meta: dict[str, Any],
) -> tuple[float, Optional[FailureDetail], dict[str, Any]]:
    """Run 20 hidden seeds and evaluate D1 differential check + invariants I1-I4."""
    profile = meta.get("profile", "replace_heavy")
    seeds = get_task_seeds(task_id, 20)
    cfg = EngineConfig()
    passed_seeds = 0
    first_failure: Optional[FailureDetail] = None
    min_triggers = 9999

    is_f3 = (meta.get("family") == "F3")
    for seed in seeds:
        trace = generate_trace(seed=seed, profile=profile, num_events=200, clean_fix=is_f3)
        min_triggers = min(min_triggers, trace.trigger_count)

        ref_engine = Engine(cfg, trace.accounts, trace.mark_price)
        try:
            cand_engine = cand_engine_cls(cfg, trace.accounts, trace.mark_price)
        except Exception as e:
            if not first_failure:
                first_failure = FailureDetail(
                    seed=seed, event_index=0, invariant="CRASH",
                    plain_name="Engine crash", message=str(e), diff={},
                )
            continue

        seed_ok = True
        for idx, event in enumerate(trace.events):
            hash_before_basket = None
            if meta.get("family") == "F5" and event.kind == "BASKET":
                hash_before_basket = cand_engine.state_hash()

            ref_reps = ref_engine.process(event)
            try:
                cand_reps = cand_engine.process(event)
            except Exception as e:
                seed_ok = False
                if not first_failure:
                    first_failure = FailureDetail(
                        seed=seed, event_index=idx, invariant="CRASH",
                        plain_name="Engine crash", message=str(e), diff={},
                    )
                break

            # F5 rollback law check: state hash after rollback must equal state hash before
            is_rolled_back = any(r.kind == "BASKET_ROLLED_BACK" for r in cand_reps)
            if hash_before_basket is not None and is_rolled_back:
                if cand_engine.state_hash() != hash_before_basket:
                    seed_ok = False
                    if not first_failure:
                        first_failure = FailureDetail(
                            seed=seed, event_index=idx, invariant="I1",
                            plain_name="Rollback restores complete state",
                            message=f"state hash after rolled-back basket at event {idx} differs",
                            diff={"before": hash_before_basket, "after": cand_engine.state_hash()},
                        )
                    break

            # Differential check D1: same list of reports
            if not _reports_equal(ref_reps, cand_reps):
                seed_ok = False
                if not first_failure:
                    first_failure = FailureDetail(
                        seed=seed, event_index=idx, invariant="D1",
                        plain_name="Report mismatch",
                        message=f"event {idx} report differs from reference",
                        diff={
                            "expected": [asdict(r) for r in ref_reps],
                            "actual": [asdict(r) for r in cand_reps],
                        },
                    )
                break

            # Invariant checks I1, I2, I3
            violations = check_invariants(cand_engine.state, idx, cfg)
            if violations:
                seed_ok = False
                if not first_failure:
                    v = violations[0]
                    first_failure = FailureDetail(
                        seed=seed, event_index=idx, invariant=v.invariant,
                        plain_name=v.plain_name, message=v.message, diff=v.diff,
                    )
                break

        if not seed_ok:
            continue

        # Differential check D1: final account balances, positions, resting orders
        for acc_id, ref_acc in ref_engine.state.accounts.items():
            cand_acc = cand_engine.state.accounts.get(acc_id)
            if (
                not cand_acc
                or cand_acc.free_cash != ref_acc.free_cash
                or cand_acc.locked_margin != ref_acc.locked_margin
                or cand_acc.position != ref_acc.position
            ):
                seed_ok = False
                if not first_failure:
                    first_failure = FailureDetail(
                        seed=seed, event_index=len(trace.events), invariant="D1",
                        plain_name="Final account state mismatch",
                        message=f"account {acc_id} final balance differs", diff={},
                    )
                break

        if not seed_ok:
            continue

        # Task F3 specific: Invariant I4 replay check
        if meta.get("family") == "F3":
            noisy = make_noisy_fix_trace(trace, seed)
            cand_noisy = cand_engine_cls(cfg, trace.accounts, trace.mark_price)
            for ev in noisy:
                cand_noisy.process(ev)
            if cand_noisy.state_hash() != cand_engine.state_hash():
                seed_ok = False
                if not first_failure:
                    first_failure = FailureDetail(
                        seed=seed, event_index=len(trace.events), invariant="I4",
                        plain_name="Replay gives the same state",
                        message="noisy trace produced different state hash", diff={},
                    )

        if seed_ok:
            passed_seeds += 1

    t3_score = passed_seeds / len(seeds)
    return t3_score, first_failure, {"min_trigger_events": min_triggers}


def grade_task(
    task_id: str,
    target_files: dict[str, str],
    is_candidate: bool = False,
) -> ScoreRecord:
    """Grade a candidate solution for a given task ID.

    Rule GRD-02: score = 0.2 * T1 + 0.3 * T2 + 0.5 * T3.
    """
    if is_candidate:
        ok, import_err = check_candidate_target_files(target_files)
        if not ok:
            return ScoreRecord(
                task_id=task_id,
                t1=0.0,
                t2=0.0,
                t3=0.0,
                score=0.0,
                passed=False,
                error="FORBIDDEN_IMPORT",
            )
    meta = _load_task_metadata(task_id)
    temp_dir = Path(tempfile.mkdtemp(prefix=f"grade_{task_id}_"))

    old_sys_path = list(sys.path)
    try:
        prepare_overlay(temp_dir, target_files)
        sys.path.insert(0, str(temp_dir))

        # Clear import cache for clean import
        for mod in list(sys.modules):
            if mod.startswith("exchange_core"):
                del sys.modules[mod]

        # Check importability
        try:
            core_engine_mod = importlib.import_module("exchange_core.engine")
            CandEngine = getattr(core_engine_mod, "Engine")
        except Exception as e:
            return ScoreRecord(
                task_id=task_id, t1=0.0, t2=0.0, t3=0.0, score=0.0, passed=False,
                error=f"ImportError: {e}",
            )

        # Run T1
        t1, err1 = grade_tier1(task_id, temp_dir)
        if err1:
            return ScoreRecord(
                task_id=task_id, t1=0.0, t2=0.0, t3=0.0, score=0.0, passed=False,
                error=f"Tier 1 error: {err1}",
            )

        # Run T2
        t2, err2 = grade_tier2(task_id, CandEngine, meta)
        if err2:
            return ScoreRecord(
                task_id=task_id, t1=t1, t2=0.0, t3=0.0, score=0.2 * t1, passed=False,
                error=f"Tier 2 error: {err2}",
            )

        # Run T3
        t3, first_failure, cov = grade_tier3(task_id, CandEngine, meta)

        score = round(0.2 * t1 + 0.3 * t2 + 0.5 * t3, 4)
        passed = (score == 1.0)

        failure_dict = asdict(first_failure) if first_failure else None
        return ScoreRecord(
            task_id=task_id,
            t1=t1,
            t2=t2,
            t3=t3,
            score=score,
            passed=passed,
            first_failure=failure_dict,
            coverage=cov,
        )
    finally:
        sys.path = old_sys_path
        shutil.rmtree(temp_dir, ignore_errors=True)
