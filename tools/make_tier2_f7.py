"""tools/make_tier2_f7.py
Regenerate tasks/f7_funding_b/tier2_trace.json from the reference engine.

The scenario is written by hand, one funding edge case per checkpoint. Expected values come
from the reference engine. One mark price is searched so that an account is solvent right after
a PRICE_SHOCK and falls into breach only because of the funding payment that follows.

    python tools/make_tier2_f7.py
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

P = 100_000_000
ACCOUNTS = {"A1": 1_000_000_000, "A2": 1_000_000_000, "A3": 1_000_000_000,
            "LIQ": 20_000_000_000}


def nl(acc, side, price, qty):
    return Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty)


def shock(m):
    return Event(kind="PRICE_SHOCK", mark_price=m)


def funding(rate):
    return Event(kind="FUNDING", bps=rate)


def edge_mark(eng) -> int:
    """Highest mark at which A1 (short) is still solvent."""
    cfg, acc = eng.cfg, eng.state.accounts["A1"]
    ok = lambda m: acc.free_cash + acc.position * m >= ceil_div(  # noqa: E731
        abs(acc.position) * m * cfg.maint_bps, 10_000)
    lo, hi = 100_500_000, 400_000_000
    assert ok(lo) and not ok(hi)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return lo


PREFIX = [
    (nl("A1", "SELL", P, 9), None),
    (nl("A2", "BUY", P, 4), None),
    (nl("A3", "BUY", P, 5), None),
    (shock(100_150_000), None),
    (funding(1), "chk_rounding_residual_goes_to_vault"),
    (funding(-4000), "chk_negative_rate_is_clamped_and_shorts_pay"),
    (funding(0), "chk_zero_rate_pays_nothing_but_runs_waterfall"),
    (shock(100_500_000), None),
    (funding(1), "chk_exact_tie_rounds_half_even"),
]
SUFFIX = [
    (funding(-3000), "chk_funding_pushes_account_into_liquidation"),
    (funding(2000), "chk_liq_account_receives_funding"),
]


def report_dict(r):
    d = {k: v for k, v in dataclasses.asdict(r).items() if v not in (None, 0, "")}
    d["kind"] = r.kind
    return d


def main():
    eng = Engine(EngineConfig(), dict(ACCOUNTS), P)
    for ev, _ in PREFIX:
        eng.process(ev)
    scenario = PREFIX + [(shock(edge_mark(eng)), None)] + SUFFIX

    eng = Engine(EngineConfig(), dict(ACCOUNTS), P)
    events, checkpoints = [], []
    for idx, (ev, name) in enumerate(scenario):
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
                "expected_fee_vault": st.fee_vault,
                "source": "engine",
            })
    out = {"accounts": ACCOUNTS, "mark_price": P, "events": events, "checkpoints": checkpoints}
    path = REPO_ROOT / "tasks" / "f7_funding_b" / "tier2_trace.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(events)} events, {len(checkpoints)} checkpoints)")


if __name__ == "__main__":
    main()
