"""tools/validate_graders.py
Validation suite for OrderBook-DST graders and task definitions.
Implements validation checks V1 to V8 per docs/07_GRADER_SPEC.md section 7.
"""
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore

from graders.dst_grader import grade_task  # noqa: E402


def get_reference_files(task_id: str, meta: dict[str, Any]) -> dict[str, str]:
    files = {}
    ref_dir = REPO_ROOT / "reference" / task_id
    for rel_path in meta.get("target_files", []):
        filename = Path(rel_path).name
        target_file = ref_dir / filename
        if not target_file.exists():
            raise FileNotFoundError(f"Missing reference file: {target_file}")
        files[rel_path] = target_file.read_text(encoding="utf-8")
    return files


def get_stub_files(meta: dict[str, Any]) -> dict[str, str]:
    files = {}
    for rel_path in meta.get("target_files", []):
        files[rel_path] = 'raise NotImplementedError("Task stub not implemented")\n'
    return files


def get_hardcoded_files(task_id: str, meta: dict[str, Any]) -> dict[str, str]:
    files = {}
    for rel_path in meta.get("target_files", []):
        if task_id == "f1_fee_a":
            files[rel_path] = (
                "def compute_taker_fee(volume_before, notional, cfg):\n"
                "    return 5500000\n"
                "def compute_maker_rebate(notional, cfg):\n"
                "    return 500000\n"
            )
        elif task_id == "f1_fee_b":
            files[rel_path] = (
                "from exchange_core.types import Report\n"
                "def settle_fill(engine, fill):\n"
                "    return [Report.fill(fill.buy_order_id, fill.sell_order_id, "
                "fill.price, fill.qty, fill.taker_order_id)]\n"
            )
        elif task_id == "f2_replace_a":
            files[rel_path] = (
                "from exchange_core.types import ReplaceDecision\n"
                "def decide_replace(order, new_price, new_qty, cfg):\n"
                "    leaves = new_qty - order.cum_qty\n"
                "    return ReplaceDecision(\n"
                "        ok=True, reason='', keep_priority=True, new_leaves=leaves\n"
                "    )\n"
            )
        elif task_id == "f2_replace_b":
            files[rel_path] = (
                "from exchange_core.types import Report\n"
                "def handle_replace(engine, event):\n"
                "    return [Report.replaced(event.order_id)]\n"
            )
        elif task_id == "f3_fix_a":
            files[rel_path] = (
                "from exchange_core.types import SessionOutcome\n"
                "def on_message(session, msg):\n"
                "    return SessionOutcome(to_process=[msg], reports=[])\n"
            )
        elif task_id == "f3_fix_b":
            files[rel_path] = (
                "from exchange_core.types import Report\n"
                "def handle_fix(engine, event):\n"
                "    return []\n"
            )
        elif task_id == "f4_waterfall_b":
            files[rel_path] = (
                "from exchange_core.types import Report\n"
                "def handle_shock(engine, event):\n"
                "    return [Report.mark_set(event.mark_price)]\n"
            )
        elif task_id == "f5_basket_b":
            files[rel_path] = (
                "from exchange_core.types import Report\n"
                "def handle_basket(engine, event):\n"
                "    return [Report.basket_committed()]\n"
            )
        elif task_id == "f7_funding_b":
            files[rel_path] = (
                "from exchange_core.types import Report\n"
                "def handle_funding(engine, event):\n"
                "    return [Report(kind='FUNDING_APPLIED', bps=event.bps, qty=0)]\n"
            )
        elif task_id == "f8_adl_b":
            files[rel_path] = (
                "def handle_bankruptcy(engine, account_id, pre_position):\n"
                "    return []\n"
            )
        elif task_id == "f6_match_b":
            files[rel_path] = (
                "from exchange_core.types import Report\n"
                "def handle_new_limit(engine, event):\n"
                "    return [Report.rejected('INVALID_ORDER')]\n"
            )
        else:
            files[rel_path] = "def dummy(*args, **kwargs):\n    return []\n"
    return files


def validate_debug_task(task_id: str, meta: dict[str, Any]) -> bool:
    """Checks for a "diagnose and fix" task (family F9, see tools/make_f9.py).

    D1: the reference scores 1.00 under this task id (so `grades_as` reaches the base task).
    D2: the clean-room alternative of the base task scores 1.00.
    D3: the minimal hand-written fix of the buggy file scores 1.00.
    D4: the buggy file scores below 1.00 and exactly like the mutant it was made from.
    D5: the stored symptom is what the stored visible trace produces.
    """
    from tools import make_f9

    inst = next(i for i in make_f9.INSTANCES if i["id"] == task_id)
    base = inst["base"]
    ok = True

    r_ref = grade_task(task_id, make_f9.reference_files(base), is_candidate=True)
    d1 = r_ref.score == 1.00 and r_ref.passed is True
    print(f"  [D1] Reference fix:        {'PASS' if d1 else 'FAIL'} (score={r_ref.score:.2f})")

    alt_files = {
        rel: (REPO_ROOT / "reference_alt_v2" / base / Path(rel).name).read_text(encoding="utf-8")
        for rel in meta.get("target_files", [])
    }
    r_alt = grade_task(task_id, alt_files, is_candidate=True)
    d2 = r_alt.score == 1.00 and r_alt.passed is True
    print(f"  [D2] Clean-room alt (v2):  {'PASS' if d2 else 'FAIL'} (score={r_alt.score:.2f})")

    r_fix = grade_task(task_id, make_f9.fixed_sources(inst), is_candidate=True)
    d3 = r_fix.score == 1.00 and r_fix.passed is True
    print(f"  [D3] Minimal hand fix:     {'PASS' if d3 else 'FAIL'} (score={r_fix.score:.2f})")

    r_bug = grade_task(task_id, make_f9.buggy_sources(inst), is_candidate=True)
    r_mut = grade_task(base, make_f9.mutant_files(base, inst["mutant"]), is_candidate=True)
    d4 = (
        r_bug.score < 1.00
        and r_bug.error is None
        and (r_bug.t1, r_bug.t2, r_bug.t3) == (r_mut.t1, r_mut.t2, r_mut.t3)
    )
    print(
        f"  [D4] Buggy file:           {'PASS' if d4 else 'FAIL'} "
        f"(score={r_bug.score:.2f}, T1={r_bug.t1:.2f} T2={r_bug.t2:.2f} T3={r_bug.t3:.2f})"
    )

    _, text, _ = make_f9.symptom_for(inst)
    stored = (REPO_ROOT / "tasks" / task_id / "symptom.md").read_text(encoding="utf-8")
    d5 = stored == text
    print(f"  [D5] Symptom reproduces:   {'PASS' if d5 else 'FAIL'}")

    ok = d1 and d2 and d3 and d4 and d5
    return ok


def run_validation() -> bool:
    tasks_dir = REPO_ROOT / "tasks"
    task_dirs = sorted([
        d for d in tasks_dir.iterdir() if d.is_dir() and (d / "task.toml").exists()
    ])

    if not task_dirs:
        print("No tasks found to validate.")
        return False

    print("=" * 80)
    print("ORDERBOOK-DST GRADER VALIDATION SUITE (V1 - V8)")
    print("=" * 80)

    all_passed = True
    detected_invariants: set[str] = set()

    for task_dir in task_dirs:
        task_id = task_dir.name
        task_toml = task_dir / "task.toml"
        meta: dict[str, Any] = tomli.loads(task_toml.read_text(encoding="utf-8"))

        fam, var = meta.get("family"), meta.get("variant")
        print(f"\n--- Validating Task: {task_id} (Family {fam}, Variant {var}) ---")

        if meta.get("mode") == "debug":
            if not validate_debug_task(task_id, meta):
                all_passed = False
            continue

        # V1: Reference solution scores 1.00
        t0 = time.time()
        ref_files = get_reference_files(task_id, meta)
        # Graded exactly as a model's answer is, including the import allowlist.
        r_ref = grade_task(task_id, ref_files, is_candidate=True)
        dt = time.time() - t0
        v1_ok = (r_ref.score == 1.00 and r_ref.passed is True)
        if not v1_ok:
            all_passed = False
        v1_tag = "PASS" if v1_ok else "FAIL"
        print(f"  [V1] Reference Check:      {v1_tag} (score={r_ref.score:.2f}, {dt:.2f}s)")

        # V2: Alternative implementations. reference_alt_v2/ is the clean-room one
        # (written without seeing reference/); reference_alt/ is an earlier,
        # non-independent variant kept for regression.
        for alt_name, alt_label in (
            ("reference_alt_v2", "Clean-room alt (v2)"),
            ("reference_alt", "Alt reference (v1)"),
        ):
            alt_dir = REPO_ROOT / alt_name / task_id
            if not alt_dir.exists():
                print(f"  [V2] {alt_label + ':':<22}SKIP (missing {alt_name}/{task_id})")
                if alt_name == "reference_alt_v2":
                    all_passed = False
                continue
            alt_files = {}
            for rel_path in meta.get("target_files", []):
                alt_files[rel_path] = (alt_dir / Path(rel_path).name).read_text(encoding="utf-8")
            r_alt = grade_task(task_id, alt_files, is_candidate=True)
            v2_ok = (r_alt.score == 1.00 and r_alt.passed is True)
            if not v2_ok:
                all_passed = False
            v2_tag = "PASS" if v2_ok else "FAIL"
            print(f"  [V2] {alt_label + ':':<22}{v2_tag} (score={r_alt.score:.2f})")

        # V3: Mutants match expect.toml
        mutants_dir = REPO_ROOT / "mutants" / task_id
        if mutants_dir.exists():
            mutant_dirs = sorted([
                d for d in mutants_dir.iterdir() if d.is_dir() and (d / "expect.toml").exists()
            ])
            for m_dir in mutant_dirs:
                m_name = m_dir.name
                expect_raw = (m_dir / "expect.toml").read_text(encoding="utf-8")
                expect_data = tomli.loads(expect_raw).get("expect", {})
                m_files = {}
                for rel_path in meta.get("target_files", []):
                    m_file = m_dir / Path(rel_path).name
                    if m_file.exists():
                        m_files[rel_path] = m_file.read_text(encoding="utf-8")

                r_m = grade_task(task_id, m_files, is_candidate=True)
                passed_m = r_m.passed == expect_data.get("passed", False)
                t1_ok = r_m.t1 >= (expect_data.get("t1_min", 0.0) - 0.05)
                t3_ok = r_m.t3 <= (expect_data.get("t3_max", 1.0) + 0.05)

                inv_ok = True
                if "violated" in expect_data:
                    violated_invs = expect_data["violated"]
                    if r_m.first_failure:
                        detected_inv = r_m.first_failure.get("invariant")
                        detected_invariants.add(detected_inv)
                        inv_ok = (detected_inv in violated_invs)
                    else:
                        inv_ok = False

                m_ok = (passed_m and t1_ok and t3_ok and inv_ok)
                if not m_ok:
                    all_passed = False
                inv_name = r_m.first_failure.get("invariant") if r_m.first_failure else "None"
                inv_str = f", violated={inv_name}"
                m_tag = "PASS" if m_ok else "FAIL"
                print(f"  [V3] Mutant {m_name:<26}: {m_tag} (score={r_m.score:.2f}{inv_str})")
        else:
            print("  [V3] Mutants Check:        SKIP (no mutants found)")

        # V4: Stub scores 0.00
        stub_files = get_stub_files(meta)
        r_stub = grade_task(task_id, stub_files)
        v4_ok = (r_stub.score == 0.00 and r_stub.passed is False)
        if not v4_ok:
            all_passed = False
        v4_tag = "PASS" if v4_ok else "FAIL"
        print(f"  [V4] Stub Check:           {v4_tag} (score={r_stub.score:.2f})")

        # V5: Hard-coded stub fails T3
        hc_files = get_hardcoded_files(task_id, meta)
        r_hc = grade_task(task_id, hc_files)
        v5_ok = (r_hc.score < 0.50 and r_hc.t3 < 1.0 and r_hc.passed is False)
        if not v5_ok:
            all_passed = False
        v5_tag = "PASS" if v5_ok else "FAIL"
        print(f"  [V5] Hard-coded Stub Check:{v5_tag} (score={r_hc.score:.2f}, t3={r_hc.t3:.2f})")

        # V6: Determinism across two runs
        r_det = grade_task(task_id, ref_files)
        v6_ok = (
            r_ref.score == r_det.score
            and r_ref.t1 == r_det.t1
            and r_ref.t2 == r_det.t2
            and r_ref.t3 == r_det.t3
        )
        if not v6_ok:
            all_passed = False
        v6_tag = "PASS" if v6_ok else "FAIL"
        print(f"  [V6] Determinism Check:    {v6_tag} (diff=0.00)")

        # V7: Trigger coverage >= 10
        min_cov = r_ref.coverage.get("min_trigger_events", 0) if r_ref.coverage else 0
        v7_ok = (min_cov >= 10)
        if not v7_ok:
            all_passed = False
        v7_tag = "PASS" if v7_ok else "FAIL"
        print(f"  [V7] Trigger Coverage:     {v7_tag} (min_triggers={min_cov} >= 10)")

    # V8: Invariant sensitivity
    print("\n--- Invariant Sensitivity Summary (V8) ---")
    print(f"  Detected invariants from mutant suite: {sorted(list(detected_invariants))}")
    v8_ok = ("I1" in detected_invariants and "I2" in detected_invariants)
    if not v8_ok:
        all_passed = False
    v8_tag = "PASS" if v8_ok else "FAIL"
    print(f"  [V8] Invariant Sensitivity:{v8_tag} (I1 and I2 detected)")

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL GRADER VALIDATION CHECKS (V1 - V8) PASSED SUCCESSFULLY!")
    else:
        print("SOME GRADER VALIDATION CHECKS FAILED.")
    print("=" * 80)

    return all_passed


def main() -> None:
    success = run_validation()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
