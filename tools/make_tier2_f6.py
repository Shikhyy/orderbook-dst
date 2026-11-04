"""tools/make_tier2_f6.py
Regenerate tasks/f6_match_b/tier2_trace.json from the reference engine.

The event list is written by hand to hit one matching edge case at a time; the expected
values at each checkpoint are read from the reference engine (exchange_core/), so
the file can be rebuilt after any change to the scenario:

    python tools/make_tier2_f6.py
"""
import dataclasses
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from exchange_core.config import EngineConfig  # noqa: E402
from exchange_core.engine import Engine  # noqa: E402
from exchange_core.types import Event  # noqa: E402

P = 100_000_000
T = 10_000
ACCOUNTS = {"A1": 5_000_000_000, "A2": 5_000_000_000, "A3": 5_000_000_000,
            "LIQ": 20_000_000_000}


def nl(acc, side, price, qty, flag="NONE"):
    return Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty, flag=flag)


# (event, checkpoint name or None)
SCENARIO = [
    (nl("A2", "SELL", P, 3), None),
    (nl("A3", "SELL", P, 2), None),
    (nl("A2", "SELL", P + T, 4), None),
    (nl("A1", "BUY", P - T, 2), "chk_book_built_locks"),
    (nl("A1", "BUY", P + T, 6), "chk_sweep_price_time_priority"),
    (nl("A2", "BUY", P, 1, "POST_ONLY"), "chk_post_only_rests_when_not_crossing"),
    (nl("A1", "SELL", P - T, 1, "IOC"), "chk_ioc_fully_filled_no_remainder"),
    (nl("A1", "SELL", P - T, 3, "IOC"), "chk_stp_then_ioc_remainder"),
    (nl("A3", "BUY", P + T, 1, "POST_ONLY"), "chk_post_only_rejected_when_crossing"),
    (nl("A3", "BUY", P + T, 400), "chk_margin_reject_uses_no_counter"),
    (nl("A3", "BUY", P + T, 1), "chk_counters_continue_after_rejects"),
    (Event(kind="SET_MARGIN_RATE", bps=3000), None),
    (nl("A2", "SELL", P, 5), None),
    (nl("A1", "BUY", P, 2), "chk_maker_keeps_its_own_margin_rate"),
    (nl("A3", "BUY", P + T, 10, "IOC"), "chk_ioc_sweeps_then_cancels_remainder"),
    (nl("A1", "SELL", P + 3 * T, 4), None),
    (nl("A1", "BUY", P + 3 * T, 4), "chk_stp_cancels_whole_lock_then_rests"),
    (nl("A2", "BUY", P - 2 * T, 2), None),
    (nl("A3", "SELL", P - 3 * T, 5), "chk_sell_sweeps_bids_best_first_and_rests"),
]


def report_dict(r):
    d = {k: v for k, v in dataclasses.asdict(r).items() if v not in (None, 0, "")}
    d["kind"] = r.kind
    return d


def main():
    eng = Engine(EngineConfig(), dict(ACCOUNTS), P)
    events, checkpoints = [], []
    for idx, (ev, name) in enumerate(SCENARIO):
        reports = eng.process(ev)
        events.append(dataclasses.asdict(ev))
        if name:
            st = eng.state
            checkpoints.append({
                "event_index": idx,
                "name": name,
                "expected_reports": [report_dict(r) for r in reports],
                "expected_accounts": {
                    a: {"free_cash": v.free_cash, "locked_margin": v.locked_margin,
                        "position": v.position, "volume": v.volume}
                    for a, v in st.accounts.items()
                },
                "expected_orders": {
                    str(o.order_id): {"cum_qty": o.cum_qty, "lock": o.lock,
                                      "prio_seq": o.prio_seq, "price": o.price}
                    for o in st.orders.values()
                },
                "expected_fee_vault": st.fee_vault,
                "source": "engine",
            })
    out = {"accounts": ACCOUNTS, "mark_price": P, "events": events, "checkpoints": checkpoints}
    path = REPO_ROOT / "tasks" / "f6_match_b" / "tier2_trace.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(events)} events, {len(checkpoints)} checkpoints)")


if __name__ == "__main__":
    main()
