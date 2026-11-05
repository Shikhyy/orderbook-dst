"""tools/make_f9.py
Build and check the F9 "diagnose and fix" tasks.

Each F9 task gives the model a buggy version of one handler (a sanitised copy of an
existing hand-written mutant), the specification of the original task, and a symptom: the
first divergence between the buggy engine and the reference engine on a fixed, visible
trace. The model must return the corrected file. It is graded by the normal 3-tier
grader of the original task (``grades_as`` in task.toml).

Usage:
    python tools/make_f9.py --explore          # list candidate symptoms (no files written)
    python tools/make_f9.py --write            # (re)generate tasks/f9_dbg_*/ from INSTANCES
    python tools/make_f9.py --check            # verify committed files are up to date

No model is called. Everything is deterministic.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import tomllib as tomli
except ImportError:  # pragma: no cover
    import tomli  # type: ignore

from exchange_core.types import Event  # noqa: E402
from graders.sandbox import prepare_overlay  # noqa: E402
from graders.trace_gen import generate_trace  # noqa: E402

# Visible seeds live far from every hidden seed range (hidden seeds are base + 0..19 with
# bases 1000..11000, so anything >= 90000 is disjoint).
VISIBLE_SEED_BASE = 90000

_RUNNER = r'''
import json, sys
from dataclasses import asdict
overlay, inp, out = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, overlay)
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.invariants import check_invariants
from exchange_core.types import BasketLeg, Event


def ev(d):
    d = dict(d)
    if isinstance(d.get("body"), dict):
        d["body"] = ev(d["body"])
    if isinstance(d.get("legs"), (list, tuple)):
        d["legs"] = tuple(BasketLeg(**x) if isinstance(x, dict) else x for x in d["legs"])
    return Event(**d)


data = json.load(open(inp))
cfg = EngineConfig()
eng = Engine(cfg, data["accounts"], data["mark_price"])
rows = []
for idx, e in enumerate(data["events"]):
    row = {"index": idx}
    try:
        reports = eng.process(ev(e))
    except Exception as exc:  # noqa: BLE001
        row["exception"] = type(exc).__name__ + ": " + str(exc)
        rows.append(row)
        break
    row["reports"] = [asdict(r) for r in reports]
    row["accounts"] = {k: asdict(v) for k, v in eng.state.accounts.items()}
    row["fee_vault"] = eng.state.fee_vault
    row["violations"] = [
        {"invariant": v.invariant, "plain_name": v.plain_name, "message": v.message}
        for v in check_invariants(eng.state, idx, cfg)
    ]
    rows.append(row)
json.dump(rows, open(out, "w"))
'''


# --------------------------------------------------------------------------------------
# Sanitising a mutant into the buggy source shown to the model
# --------------------------------------------------------------------------------------

_LEAK_WORDS = re.compile(r"mutant|\bbug\b|\bbuggy\b", re.IGNORECASE)


def sanitise_source(text: str, module_doc: str) -> str:
    """Remove everything in a mutant file that names the injected bug.

    Mutant files carry comments such as ``# Mutant bug: ...`` and docstrings such as
    ``Mutant that ...``. Comments and docstrings are dropped for the lines that mention the
    mutant; the module docstring is replaced by a neutral one. Behaviour is untouched
    (checked by the tests: the sanitised file grades exactly like the mutant).
    """
    tree = ast.parse(text)
    lines = text.splitlines()
    # Drop the original module docstring (lines are 1-based, end_lineno inclusive).
    drop: set[int] = set()
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(getattr(tree.body[0], "value", None), ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        first = tree.body[0]
        drop.update(range(first.lineno, first.end_lineno + 1))
    out: list[str] = [f'"""{module_doc}"""']
    for i, line in enumerate(lines, 1):
        if i in drop:
            continue
        out.append(line)
    cleaned = "\n".join(out) + "\n"
    # Remove full-line comments and trailing comments that mention the bug.
    result: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and _LEAK_WORDS.search(stripped):
            continue
        if "#" in line and _LEAK_WORDS.search(line.split("#", 1)[1]):
            line = line.split("#", 1)[0].rstrip()
        result.append(line)
    text2 = "\n".join(result) + "\n"
    # Collapse more than two blank lines left behind.
    text2 = re.sub(r"\n{4,}", "\n\n\n", text2)
    return text2


def strip_comments_and_docstrings(text: str) -> str:
    """Canonical form used to compare two sources for equal behaviour-bearing code."""
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


# --------------------------------------------------------------------------------------
# Running a trace against an overlay (reference or buggy) in an isolated subprocess
# --------------------------------------------------------------------------------------


def simulate(
    files: dict[str, str], accounts: dict[str, int], mark_price: int, events: list[Any]
) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="f9sim_") as tmp:
        tmp_path = Path(tmp)
        overlay = tmp_path / "overlay"
        overlay.mkdir()
        prepare_overlay(overlay, files)
        inp = tmp_path / "in.json"
        outp = tmp_path / "out.json"
        inp.write_text(
            json.dumps(
                {
                    "accounts": accounts,
                    "mark_price": mark_price,
                    "events": [asdict(e) for e in events],
                }
            ),
            encoding="utf-8",
        )
        runner = tmp_path / "runner.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-I", str(runner), str(overlay), str(inp), str(outp)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"simulation failed: {proc.stderr[-800:]}")
        rows: list[dict[str, Any]] = json.loads(outp.read_text(encoding="utf-8"))
        return rows


# --------------------------------------------------------------------------------------
# Symptom extraction and rendering
# --------------------------------------------------------------------------------------


def _compact(d: dict[str, Any], defaults: dict[str, Any]) -> str:
    parts = []
    for k, v in d.items():
        if k == "kind":
            continue
        if v == defaults.get(k) or v in (None, (), []):
            continue
        parts.append(f"{k}={v}")
    return f"{d['kind']}(" + ", ".join(parts) + ")"


_REPORT_DEFAULTS: dict[str, Any] = {
    "order_id": 0, "reason": "", "buy_order_id": 0, "sell_order_id": 0, "price": 0, "qty": 0,
    "taker_order_id": 0, "account": "", "mark_price": 0, "bps": 0, "session": "", "leg_index": 0,
}
_EVENT_DEFAULTS: dict[str, Any] = {
    "account": "", "side": "", "price": 0, "qty": 0, "flag": "NONE", "order_id": 0,
    "new_price": 0, "new_qty": 0, "bps": 0, "mark_price": 0, "session": "", "epoch": 0,
    "seq": 0, "poss_dup": False, "body": None, "legs": [],
}


def render_event(e: Any) -> str:
    d = asdict(e)
    d["legs"] = [dict(x) for x in d.get("legs") or []]
    return _compact(d, _EVENT_DEFAULTS)


def render_report(r: dict[str, Any]) -> str:
    return _compact(r, _REPORT_DEFAULTS)


def find_symptom(
    ref_rows: list[dict[str, Any]], bug_rows: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """First externally visible divergence: crash, report mismatch, invariant breach.

    If none of these shows up on the whole trace, fall back to the first difference in
    account balances or the fee vault (a "regression test" style symptom).
    """
    for idx, (rr, br) in enumerate(zip(ref_rows, bug_rows)):
        if "exception" in br:
            return {"kind": "crash", "index": idx, "message": br["exception"]}
        if rr["reports"] != br["reports"]:
            return {
                "kind": "reports", "index": idx,
                "expected": rr["reports"], "actual": br["reports"],
            }
        if br["violations"]:
            return {"kind": "invariant", "index": idx, "violations": br["violations"]}
    for idx, (rr, br) in enumerate(zip(ref_rows, bug_rows)):
        for acc, ra in rr["accounts"].items():
            ba = br["accounts"].get(acc, {})
            for field in ("free_cash", "locked_margin", "position", "volume"):
                if ra[field] != ba.get(field):
                    return {
                        "kind": "state", "index": idx, "what": f"account {acc} {field}",
                        "expected": ra[field], "actual": ba.get(field),
                    }
        if rr["fee_vault"] != br["fee_vault"]:
            return {
                "kind": "state", "index": idx, "what": "fee_vault",
                "expected": rr["fee_vault"], "actual": br["fee_vault"],
            }
    return None


def render_symptom(
    sym: dict[str, Any], events: list[Any], accounts: dict[str, int], mark_price: int
) -> str:
    idx = sym["index"]
    lines = [
        "## Bug Report",
        "",
        "The engine in the \"Buggy Target Files\" section violates the specification. "
        "It was run on a short fixed event trace. All numbers are integers.",
        "",
        "Initial state: " + ", ".join(f"{k} free_cash={v}" for k, v in accounts.items())
        + f"; mark_price={mark_price}; all positions 0; no resting orders; fee_vault=0.",
        "",
        "Events (0-based index; the engine processes them in order):",
        "",
    ]
    for i, e in enumerate(events[: idx + 1]):
        lines.append(f"{i}. {render_event(e)}")
    lines.append("")
    kind = sym["kind"]
    if kind == "crash":
        lines.append(f"Symptom: the engine raised an exception at event {idx}: {sym['message']}")
    elif kind == "reports":
        lines.append(f"Symptom: at event {idx} the engine returned the wrong reports.")
        lines.append("")
        lines.append("Expected reports:")
        lines += [f"- {render_report(r)}" for r in sym["expected"]] or ["- (none)"]
        lines.append("")
        lines.append("Actual reports:")
        lines += [f"- {render_report(r)}" for r in sym["actual"]] or ["- (none)"]
    elif kind == "invariant":
        v = sym["violations"][0]
        lines.append(
            f"Symptom: after event {idx} the invariant \"{v['plain_name']}\" is broken: "
            f"{v['message']}."
        )
    else:
        lines.append(
            f"Symptom: after event {idx} the state differs from the specified outcome: "
            f"{sym['what']} is {sym['actual']}, expected {sym['expected']}."
        )
    lines.append("")
    lines.append(
        "Find the defect in the target file and return the corrected file. Change only what "
        "the specification requires; every other behaviour must stay exactly as it is."
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------
# Instances
# --------------------------------------------------------------------------------------


def _fee_cross_trace() -> tuple[dict[str, int], int, list[Event]]:
    """Hand-written visible trace: A1 buys 49 units (notional 4.9e9, just below the fee-tier
    threshold of 5,000,010,000) from A2. The fee of that single fill depends on whether A1's
    volume already contains the fill when the fee is computed."""
    accounts = {"A1": 20_000_000_000, "A2": 20_000_000_000, "LIQ": 100_000_000_000}
    p = 100_000_000
    events = [
        Event(kind="NEW_LIMIT", account="A2", side="SELL", price=p, qty=49),
        Event(kind="NEW_LIMIT", account="A1", side="BUY", price=p, qty=49),
    ]
    return accounts, p, events


HANDCRAFTED = {"fee_cross": _fee_cross_trace}

INSTANCES: list[dict[str, Any]] = [
    {
        "id": "f9_dbg_1",
        "base": "f1_fee_b",
        "mutant": "m_volume_before_fee",
        "trace": "handcrafted:fee_cross",
        "n_events": 2,
        "drop_lines": [],
        "fix": [
            (
                "    state.accounts[fill.buyer].volume += notional\n"
                "    state.accounts[fill.seller].volume += notional\n\n"
                "    volume_before",
                "    volume_before",
            ),
            (
                "    state.fee_vault += (fee - rebate)\n",
                "    state.fee_vault += (fee - rebate)\n\n"
                "    state.accounts[fill.buyer].volume += notional\n"
                "    state.accounts[fill.seller].volume += notional\n",
            ),
        ],
        "bug": "Both accounts' volume is increased before the taker fee is computed, so the "
        "fee tier is chosen from a volume that already contains the current fill (R-F1).",
        "symptom_why": "No report, invariant or conservation check can see it: the FILL report "
        "is correct and money is conserved (the fee goes to the vault either way). Only the "
        "taker's cash differs, and only for a fill that crosses the tier threshold.",
        "fix_why": "R-F1 says volume is added after the fee is computed, so the single correct "
        "place for the two volume lines is after the fee and rebate settlement. Any correct "
        "fix reproduces the reference state.",
    },
    {
        "id": "f9_dbg_2",
        "base": "f4_waterfall_b",
        "mutant": "m_no_recheck_after_cancel",
        "trace": 90030,
        "n_events": 25,
        "drop_lines": [],
        "fix": [
            (
                '            reports.append(Report.cancelled(o.order_id, "RISK"))\n',
                '            reports.append(Report.cancelled(o.order_id, "RISK"))\n\n'
                "        # Stage 1 may have cured the breach.\n"
                "        if acc.free_cash + acc.position * state.mark_price >= req:\n"
                "            continue\n",
            ),
        ],
        "bug": "After stage 1 the breach test is not repeated, so an account whose cancelled "
        "orders released enough margin is still liquidated (R-W4).",
        "symptom_why": "The symptom is one extra LIQUIDATED report at the last event of an "
        "11-event trace; it does not say which rule was skipped or that stage 1 had "
        "cancelled orders first. (The public tests, which the model cannot run, do cover "
        "the case.)",
        "fix_why": "R-W4 requires the same breach test with the new free_cash; liquidation only "
        "if still in breach. The corrected behaviour is fully determined by R-W2 and R-W4.",
    },
    {
        "id": "f9_dbg_3",
        "base": "f5_basket_b",
        "mutant": "m_forgot_counter_restore",
        "trace": 90006,
        "n_events": 25,
        "drop_lines": [],
        "fix": [
            (
                "    next_id = engine.state.next_order_id\n"
                "    engine.state.restore(snap)\n"
                "    engine.state.next_order_id = next_id\n",
                "    engine.state.restore(snap)\n",
            ),
        ],
        "bug": "A rolled-back basket keeps the advanced order-id counter instead of restoring "
        "the whole snapshot (R-A4).",
        "symptom_why": "The rolled-back basket itself reports correctly. The first visible effect "
        "is an order id that is too large in a later ACCEPTED report, an event after the "
        "rollback, so the cause has to be traced back to the rollback path.",
        "fix_why": "R-A4 restores the complete state snapshot; restoring the counter as well "
        "is the only way to reproduce the reference order ids.",
    },
    {
        "id": "f9_dbg_4",
        "base": "f6_match_b",
        "mutant": "m_maker_lock_stale",
        "trace": 90006,
        "n_events": 25,
        "drop_lines": [],
        "fix": [
            (
                "        if best_resting.leaves == 0:\n"
                "            best_resting.lock = maker_new_lock\n",
                "        best_resting.lock = maker_new_lock\n",
            ),
        ],
        "bug": "A partially filled resting order releases margin to the account but keeps its "
        "old stored lock (R-M4 step 4).",
        "symptom_why": "The reports are all correct; the symptom is a margin invariant on the "
        "resting order after a partial fill. Fully filled orders are fine, so simple fills "
        "do not show it, and the visible tests pass.",
        "fix_why": "R-M4 step 4 stores new_lock in the order for both sides of every fill; the "
        "condition on leaves has no support in the rules.",
    },
    {
        "id": "f9_dbg_5",
        "base": "f7_funding_b",
        "mutant": "m_residual_not_to_vault",
        "trace": 90026,
        "n_events": 25,
        "drop_lines": [
            "    # Rule R-Y3: the rounding residual goes to the fee vault",
            "    pass",
        ],
        "fix": [
            (
                "    # Rule R-Y4: FUNDING_APPLIED report",
                "    state.fee_vault += residual\n\n    # Rule R-Y4: FUNDING_APPLIED report",
            ),
        ],
        "bug": "The net of the per-account payments (the rounding residual) is computed but "
        "never added to the fee vault, so total money drifts by the residual (R-Y3).",
        "symptom_why": "The numbers are off by a few micro-units of cash, long after the first "
        "FUNDING event that caused it, and the reports are correct. The code that is missing "
        "is an omission, so there is no wrong line to point at (an accumulator is left "
        "unused, which is the one hint).",
        "fix_why": "R-Y3 states that the net of payments and receipts goes to the fee vault, "
        "keeping cash plus vault constant. Booking it is the only conserving fix.",
    },
    {
        "id": "f9_dbg_6",
        "base": "f8_adl_b",
        "mutant": "m_leftover_largest_remainder",
        "trace": 90004,
        "n_events": 25,
        "drop_lines": [],
        "fix": [
            (
                "key=lambda a: (-(remaining * weights[a] % total), a)",
                "key=lambda a: (-weights[a], a)",
            ),
        ],
        "bug": "The leftover units after floor division go to the largest fractional remainders "
        "(the textbook method) instead of the largest weights (R-L3).",
        "symptom_why": "Shares differ by one unit between the same accounts, only when the "
        "weights and remainders rank differently. Money is still conserved, so no invariant "
        "fires, and the method used is a plausible one.",
        "fix_why": "R-L3 fixes the ranking: descending weight, ties by ascending account id. "
        "No other ordering reproduces the reference.",
    },
]


def load_base(base_task: str) -> dict[str, Any]:
    return tomli.loads((REPO_ROOT / "tasks" / base_task / "task.toml").read_text())


def mutant_files(base_task: str, mutant: str) -> dict[str, str]:
    meta = load_base(base_task)
    m_dir = REPO_ROOT / "mutants" / base_task / mutant
    files = {}
    for rel in meta["target_files"]:
        files[rel] = (m_dir / Path(rel).name).read_text(encoding="utf-8")
    return files


def reference_files(base_task: str) -> dict[str, str]:
    meta = load_base(base_task)
    return {
        rel: (REPO_ROOT / "reference" / base_task / Path(rel).name).read_text(encoding="utf-8")
        for rel in meta["target_files"]
    }


def visible_trace(base_task: str, seed: int, n_events: int) -> Any:
    meta = load_base(base_task)
    return generate_trace(
        seed=seed, profile=meta["profile"], num_events=n_events,
        clean_fix=meta.get("family") == "F3",
    )


def _stub_module_doc(rel_path: str) -> str:
    """Neutral module docstring: the path only, so it cannot hint at the defect."""
    return rel_path


def _trace_for(inst: dict[str, Any]) -> tuple[dict[str, int], int, list[Any]]:
    trace = inst["trace"]
    if isinstance(trace, str) and trace.startswith("handcrafted:"):
        return HANDCRAFTED[trace.split(":", 1)[1]]()
    tr = visible_trace(inst["base"], int(trace), inst["n_events"])
    return tr.accounts, tr.mark_price, tr.events


def buggy_sources(inst: dict[str, Any]) -> dict[str, str]:
    out = {}
    for rel, text in mutant_files(inst["base"], inst["mutant"]).items():
        kept = [ln for ln in text.splitlines() if ln not in inst["drop_lines"]]
        out[rel] = sanitise_source("\n".join(kept) + "\n", _stub_module_doc(rel))
    return out


def fixed_sources(inst: dict[str, Any]) -> dict[str, str]:
    """The minimal hand-written fix, applied to the sanitised buggy source."""
    out = {}
    for rel, text in buggy_sources(inst).items():
        for old, new in inst["fix"]:
            if text.count(old) != 1:
                raise ValueError(f"{inst['id']}: fix anchor found {text.count(old)}x: {old!r}")
            text = text.replace(old, new)
        out[rel] = text
    return out


def symptom_for(inst: dict[str, Any]) -> tuple[dict[str, Any], str, list[Any]]:
    accounts, mark, events = _trace_for(inst)
    ref = simulate(reference_files(inst["base"]), accounts, mark, events)
    bug = simulate(mutant_files(inst["base"], inst["mutant"]), accounts, mark, events)
    sym = find_symptom(ref, bug)
    if sym is None:
        raise ValueError(f"{inst['id']}: the visible trace shows no symptom")
    return sym, render_symptom(sym, events, accounts, mark), events


def _instruction(inst: dict[str, Any]) -> str:
    base_text = (REPO_ROOT / "tasks" / inst["base"] / "instruction.md").read_text(
        encoding="utf-8"
    )
    marker = "## 2."
    if marker not in base_text:
        raise ValueError(f"{inst['base']}: instruction has no '## 2.' heading")
    spec = base_text[base_text.index(marker):]
    meta = load_base(inst["base"])
    rel = meta["target_files"][0]
    head = (
        f"# Task {inst['id']}: Diagnose and Fix\n\n"
        "## 1. Goal\n"
        f"The file `{rel}` (shown in the section \"Buggy Target Files\" below) was written "
        "for the specification in section 2. It contains **one defect**. The \"Bug Report\" "
        "section gives a short event trace and the first thing that goes wrong when the "
        "engine runs it.\n\n"
        "Find the defect and return the complete corrected file in the usual `### FILE:` "
        "format. Change only what the specification requires: every other behaviour must "
        "stay exactly as it is. The file is graded like an ordinary implementation: the "
        "public tests (shown in full in the \"Public Tests (Visible)\" section), targeted "
        "checkpoints and hidden event traces are all compared with the behaviour the "
        "specification defines.\n\n"
    )
    return head + spec


def _task_toml(inst: dict[str, Any]) -> str:
    meta = load_base(inst["base"])
    targets = ", ".join(f'"{t}"' for t in meta["target_files"])
    rules = ", ".join(f'"{r}"' for r in meta["rules"])
    reason = (
        "Diagnosis instead of implementation: the model gets the specification, a handler "
        "with one injected defect and the first failing step of a short trace, and has to "
        f"localise and fix it. {inst['symptom_why']}"
    ).replace('"', "'")
    return (
        f'id = "{inst["id"]}"\n'
        'family = "F9"\n'
        'variant = "debug"\n'
        'mode = "debug"\n'
        f'grades_as = "{inst["base"]}"\n'
        f'source_mutant = "{inst["base"]}/{inst["mutant"]}"\n'
        f"target_files = [{targets}]\n"
        f"rules = [{rules}]\n"
        f'profile = "{meta["profile"]}"\n'
        f"timeout_s = {meta.get('timeout_s', 60)}\n"
        f'difficulty_reason = "{reason}"\n'
        "author_signoff = false\n"
    )


def build_instance(inst: dict[str, Any]) -> dict[str, str]:
    """Every file of one F9 task, as {path relative to the repo root: content}."""
    sym, text, events = symptom_for(inst)
    tid = inst["id"]
    files = {
        f"tasks/{tid}/task.toml": _task_toml(inst),
        f"tasks/{tid}/instruction.md": _instruction(inst),
        f"tasks/{tid}/symptom.md": text,
        f"tasks/{tid}/symptom_meta.json": json.dumps(
            {
                "trace": inst["trace"], "n_events": inst["n_events"], "kind": sym["kind"],
                "index": sym["index"], "source_mutant": f"{inst['base']}/{inst['mutant']}",
            },
            indent=2,
        )
        + "\n",
    }
    for rel, src in buggy_sources(inst).items():
        files[f"tasks/{tid}/buggy/{rel}"] = src
    return files


def instances_doc() -> str:
    lines = [
        "# F9 instances: diagnose and fix",
        "",
        "Generated by `tools/make_f9.py --write`. Do not edit by hand.",
        "",
        "Each task hands the model the specification of an existing task, a handler with one "
        "defect (a sanitised copy of an existing hand-written mutant) and the first failing "
        "step of a visible trace. It is graded by the grader of the original task. The prompt "
        "contains nothing that names the mutant or shows the fix.",
        "",
        "| Task | Graded as | Defect | Symptom kind | Tier that catches the bug |",
        "|---|---|---|---|---|",
    ]
    for inst in INSTANCES:
        sym, _, _ = symptom_for(inst)
        lines.append(
            f"| `{inst['id']}` | `{inst['base']}` | {inst['bug']} | {sym['kind']} "
            f"(event {sym['index']}) | see `results/grader_analysis/mutant_tiers.md` "
            f"(`{inst['mutant']}`) |"
        )
    for inst in INSTANCES:
        lines += [
            "",
            f"## {inst['id']} ({inst['base']} / {inst['mutant']})",
            "",
            f"- **Defect.** {inst['bug']}",
            f"- **Why the symptom is not obvious.** {inst['symptom_why']}",
            f"- **Why the fix is unique.** {inst['fix_why']}",
        ]
    return "\n".join(lines) + "\n"


def all_outputs() -> dict[str, str]:
    out: dict[str, str] = {}
    for inst in INSTANCES:
        out.update(build_instance(inst))
    out["docs/F9_INSTANCES.md"] = instances_doc()
    return out


def explore(candidates: list[tuple[str, str]], seeds: range, n_events: int) -> None:
    """Print the first few visible seeds that show a symptom, for choosing instances."""
    for base, mutant in candidates:
        ref = reference_files(base)
        bug = mutant_files(base, mutant)
        print(f"=== {base}/{mutant}")
        found = []
        for s in seeds:
            tr = visible_trace(base, s, n_events)
            rr = simulate(ref, tr.accounts, tr.mark_price, tr.events)
            br = simulate(bug, tr.accounts, tr.mark_price, tr.events)
            sym = find_symptom(rr, br)
            if sym is not None:
                found.append((sym["index"], s, sym["kind"]))
        found.sort()
        print("  (index, seed, kind):", found[:6])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--explore", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--candidates", nargs="*", default=[])
    ap.add_argument("--seed-start", type=int, default=VISIBLE_SEED_BASE)
    ap.add_argument("--seed-count", type=int, default=30)
    ap.add_argument("--events", type=int, default=40)
    args = ap.parse_args()
    if args.explore:
        cands = [tuple(c.split("/", 1)) for c in args.candidates]
        explore(cands, range(args.seed_start, args.seed_start + args.seed_count), args.events)
        return 0
    if args.write:
        for rel, content in all_outputs().items():
            path = REPO_ROOT / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print("wrote", rel)
        return 0
    if args.check:
        stale = [
            rel for rel, content in all_outputs().items()
            if not (REPO_ROOT / rel).exists()
            or (REPO_ROOT / rel).read_text(encoding="utf-8") != content
        ]
        if stale:
            print("stale or missing:", *stale, sep="\n  ")
            return 1
        print("F9 files are up to date")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
