"""tools/make_tier2_f4_boundary.py
Extend tasks/f4_waterfall_b/tier2_trace.json with two exact-boundary checkpoints (rules R-W2, R-W4).

The original 21 events and 6 checkpoints are kept. The account "A4" is added to the initial
accounts, so every old checkpoint gains an "A4" entry; this script asserts that nothing else in
the old checkpoints changes. Then it appends:

  chk_stage1_exact_requirement_is_not_breach
      "A4" is short 1 and holds a resting BUY. At the mark of the shock it is in breach, stage 1
      cancels the order, and the new available equity is EXACTLY the maintenance requirement. R-W4
      says the account is then not in breach: no liquidation. A re-test written with `>` instead
      of `>=` liquidates it.
  chk_exact_requirement_at_first_test_is_not_breach
      The same shock again: the available equity now equals the requirement before stage 1.
      R-W2: not in breach, nothing happens.

Expected values come from the reference engine, and the properties above are asserted.

    python tools/make_tier2_f4_boundary.py
"""
import dataclasses
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from exchange_core.config import EngineConfig  # noqa: E402
from exchange_core.engine import Engine  # noqa: E402
from exchange_core.intmath import ceil_div  # noqa: E402
from exchange_core.types import Event  # noqa: E402

PATH = REPO_ROOT / "tasks" / "f4_waterfall_b" / "tier2_trace.json"
ORIGINAL_EVENTS = 21
ORIGINAL_CHECKPOINTS = 6
P = 100_000_000


def report_dict(r):
    d = {k: v for k, v in dataclasses.asdict(r).items() if v not in (None, 0, "")}
    d["kind"] = r.kind
    return d


def matches_in_order(expected, reports):
    """The grader's rule for `expected_reports`: each expected report (compared on the fields
    it lists) must be found in the reports, in the same order; extra reports are allowed."""
    pos = 0
    for exp in expected:
        for pos_i in range(pos, len(reports)):
            r = reports[pos_i]
            if r.kind == exp.get("kind") and all(getattr(r, k, None) == v
                                                 for k, v in exp.items()):
                pos = pos_i + 1
                break
        else:
            return False
    return True


def snapshot(eng):
    return {
        "expected_accounts": {
            a: {"free_cash": v.free_cash, "locked_margin": v.locked_margin,
                "position": v.position, "volume": v.volume}
            for a, v in eng.state.accounts.items()
        },
        "expected_fee_vault": eng.state.fee_vault,
    }


def simulate(accounts, events):
    """Run all events on a fresh reference engine; return (engine, reports per event)."""
    eng = Engine(EngineConfig(), dict(accounts), P)
    reps = [eng.process(e if isinstance(e, Event) else Event(**e)) for e in events]
    return eng, reps


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    original = data["events"][:ORIGINAL_EVENTS]
    old_cps = [c for c in data["checkpoints"] if c["event_index"] < ORIGINAL_EVENTS]
    assert len(old_cps) == ORIGINAL_CHECKPOINTS, len(old_cps)
    base_accounts = {a: v for a, v in data["accounts"].items() if a != "A4"}
    cfg = EngineConfig()

    # The boundary shock uses the mark at the end of the original trace, so that the other
    # accounts stay in the state they had before.
    probe, _ = simulate(base_accounts, original)
    mark = probe.state.mark_price
    req = ceil_div(1 * mark * cfg.maint_bps, 10_000)
    needed = mark + req  # free cash "A4" needs after the cancel: cash + (-1) * mark == req

    tail = [
        Event(kind="NEW_LIMIT", account="LIQ", side="BUY", price=P, qty=1),
        Event(kind="NEW_LIMIT", account="A4", side="SELL", price=P, qty=1),
        Event(kind="NEW_LIMIT", account="A4", side="BUY", price=P - 5 * 10_000, qty=1),
    ]
    shock = Event(kind="PRICE_SHOCK", mark_price=mark)
    events = original + [dataclasses.asdict(e) for e in tail + [shock, shock]]

    # Initial cash of "A4" for which free_cash + lock - mark == req exactly after the fill
    trial_eng, _ = simulate(dict(base_accounts, A4=3 * P), original + tail)
    a4 = trial_eng.state.accounts["A4"]
    assert a4.position == -1 and a4.locked_margin > 0, (a4.position, a4.locked_margin)
    start = 3 * P + (needed - (a4.free_cash + a4.locked_margin))
    accounts = dict(base_accounts, A4=start)

    pre_eng, _ = simulate(accounts, original + tail)
    a4 = pre_eng.state.accounts["A4"]
    assert a4.free_cash + a4.locked_margin - mark == req, "A4 is not exactly on the boundary"
    assert a4.free_cash - mark < req, "A4 must be in breach before the cancel"

    eng, reps = simulate(accounts, events)
    i1, i2 = len(events) - 2, len(events) - 1
    kinds1 = [r.kind for r in reps[i1]]
    kinds2 = [r.kind for r in reps[i2]]
    assert kinds1 == ["MARK_SET", "CANCELLED"], kinds1  # cancelled, NOT liquidated
    assert kinds2 == ["MARK_SET"], kinds2
    assert eng.state.accounts["A4"].position == -1

    # Old checkpoints must be unchanged apart from the new account entry
    old_eng = Engine(EngineConfig(), dict(accounts), P)
    for idx, e in enumerate(original):
        rep = old_eng.process(Event(**e))
        for cp in old_cps:
            if cp["event_index"] != idx:
                continue
            snap = snapshot(old_eng)
            assert matches_in_order(cp["expected_reports"], rep), cp["name"]
            assert snap["expected_fee_vault"] == cp["expected_fee_vault"], cp["name"]
            got = {a: v for a, v in snap["expected_accounts"].items() if a != "A4"}
            assert got == cp["expected_accounts"], cp["name"]
            cp["expected_accounts"] = snap["expected_accounts"]

    def checkpoint(idx, name):
        e = Engine(EngineConfig(), dict(accounts), P)
        for ev in events[: idx + 1]:
            last = e.process(Event(**ev))
        return {"event_index": idx, "name": name,
                "expected_reports": [report_dict(r) for r in last],
                **snapshot(e), "source": "engine"}

    new_cps = [
        checkpoint(i1, "chk_stage1_exact_requirement_is_not_breach"),
        checkpoint(i2, "chk_exact_requirement_at_first_test_is_not_breach"),
    ]
    out = {"accounts": accounts, "mark_price": P, "events": events,
           "checkpoints": old_cps + new_cps}
    PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {PATH} ({len(events)} events, {len(out['checkpoints'])} checkpoints)")


if __name__ == "__main__":
    main()
