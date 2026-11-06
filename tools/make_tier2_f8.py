"""tools/make_tier2_f8.py
Regenerate tasks/f8_adl_b/tier2_trace.json from the reference engine.

The scenario is written by hand, one bankruptcy edge case per checkpoint. A live reference engine
runs while the events are chosen: each crash mark is searched so that the deficit has the property
the case needs (small enough for the fee vault, a remainder that leaves leftover units, a weight
tie at the cut, ...). Every property is asserted below, so a change of the engine cannot silently
turn a checkpoint into a different case. Expected values come from the reference engine.

    python tools/make_tier2_f8.py
"""
import copy
import dataclasses
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from exchange_core.config import EngineConfig  # noqa: E402
from exchange_core.engine import Engine  # noqa: E402
from exchange_core.invariants import check_invariants  # noqa: E402
from exchange_core.types import Event  # noqa: E402

P = 100_000_000
THIN = 410_000_000  # buying 6 units at P with the default 20% lock leaves negative cash
ACCOUNTS = {
    "A1": 3_000_000_000, "A2": 3_000_000_000, "A3": 3_000_000_000, "A10": 3_000_000_000,
    "A11": THIN, "A12": THIN, "A13": THIN, "A14": THIN, "A15": THIN, "A5": THIN,
    "A6": THIN, "A7": THIN, "A8": THIN,
    "A16": 40_000_000,  # the lock of 36 units at a 1% rate is 36,000,000: nearly no capital
    "A4": 32_000_000,   # the lock of a 31-unit short is 31,000,000: nearly no capital of its own
    "A0": 6_000_000,    # a 5-unit short (lock 5,000,000), examined before "A16" by the waterfall
    "LIQ": 50_000_000_000,
}
POOL = ("A1", "A2", "A3", "A10")


class NeedAdjust(Exception):
    """The initial cash of "A7" has to change by `adj` so that a deficit can leave exactly 2."""

    def __init__(self, adj):
        super().__init__(adj)
        self.adj = adj


def nl(acc, side, qty):
    return Event(kind="NEW_LIMIT", account=acc, side=side, price=P, qty=qty)


def crash(mark):
    return Event(kind="PRICE_CRASH", mark_price=mark)


def report_dict(r):
    d = {k: v for k, v in dataclasses.asdict(r).items() if v not in (None, 0, "")}
    d["kind"] = r.kind
    return d


def kinds(reports):
    return [r.kind for r in reports if r.kind != "MARK_SET"]


def split(remaining, weights):
    """Independent re-derivation of R-L3: shares and the number of leftover units."""
    total = sum(weights.values())
    base = {a: remaining * w // total for a, w in weights.items()}
    leftover = remaining - sum(base.values())
    ranked = sorted(weights, key=lambda a: (-weights[a], a))
    shares = dict(base)
    for a in ranked[:leftover]:
        shares[a] += 1
    return shares, leftover, ranked


def split_largest_remainder(remaining, weights):
    """The textbook alternative (a wrong reading of R-L3): leftover units go to the largest
    fractional remainders. The checkpoints must tell it apart from the declared rule."""
    total = sum(weights.values())
    shares = {a: remaining * w // total for a, w in weights.items()}
    leftover = remaining - sum(shares.values())
    ranked = sorted(weights, key=lambda a: (-(remaining * weights[a] % total), a))
    for a in ranked[:leftover]:
        shares[a] += 1
    return shares


def _vault_after_funding(eng, rate):
    probe = copy.deepcopy(eng)
    probe.process(Event(kind="FUNDING", bps=rate))
    return probe.state.fee_vault


class Scenario:
    def __init__(self):
        self.eng = Engine(EngineConfig(), dict(ACCOUNTS), P)
        self.events: list[dict] = []
        self.checkpoints: list[dict] = []

    @property
    def st(self):
        return self.eng.state

    def do(self, ev, name=None, exact=False):
        reports = self.eng.process(ev)
        assert not check_invariants(self.st, len(self.events)), "invariant broken in scenario"
        idx = len(self.events)
        self.events.append(dataclasses.asdict(ev))
        if name:
            self.checkpoints.append({
                "event_index": idx,
                "name": name,
                "expected_reports": [report_dict(r) for r in reports],
                "expected_accounts": {
                    a: {"free_cash": v.free_cash, "locked_margin": v.locked_margin,
                        "position": v.position, "volume": v.volume}
                    for a, v in self.st.accounts.items()
                },
                "expected_fee_vault": self.st.fee_vault,
                "source": "engine",
                **({"exact_reports": True} if exact else {}),
            })
        return reports

    def sweep(self, taker, side, makers):
        """Makers rest on the other side at P, then the taker order sweeps all of them."""
        other = "SELL" if side == "BUY" else "BUY"
        for acc, qty in makers:
            reps = self.do(nl(acc, other, qty))
            assert kinds(reps) == ["ACCEPTED"], (acc, kinds(reps))
        reps = self.do(nl(taker, side, sum(q for _, q in makers)))
        assert kinds(reps) == ["ACCEPTED"] + ["FILL"] * len(makers), kinds(reps)

    def flatten(self):
        """Unwind every pool position against LIQ at P (no crash, no mark change)."""
        for acc in POOL:
            pos = self.st.accounts[acc].position
            if pos < 0:
                self.do(nl("LIQ", "SELL", -pos))
                self.do(nl(acc, "BUY", -pos))
            elif pos > 0:
                self.do(nl("LIQ", "BUY", pos))
                self.do(nl(acc, "SELL", pos))
            assert self.st.accounts[acc].position == 0, acc

    def weights(self, x):
        pre = self.st.accounts[x].position
        return {a: abs(v.position) for a, v in self.st.accounts.items()
                if a not in ("LIQ", x) and v.position != 0 and (v.position > 0) != (pre > 0)}

    def deficit_at(self, x, mark):
        a = self.st.accounts[x]
        return max(0, -(a.free_cash + a.position * mark))

    def find_mark(self, x, pred, lo, hi):
        """First mark in [lo, hi], scanned in the direction that deepens the loss, for which x
        would end with a deficit d satisfying pred(d, vault)."""
        a = self.st.accounts[x]
        marks = range(hi, lo - 1, -1) if a.position > 0 else range(lo, hi + 1)
        for m in marks:
            d = self.deficit_at(x, m)
            if pred(d, self.st.fee_vault):
                return m
        raise AssertionError(f"no mark found for {x}")


def main() -> Scenario:  # noqa: C901 - one linear script, one block per case
    sc = Scenario()
    st = sc.st

    # chk1: the only counterparty is LIQ (never eligible). Insurance pays what the vault holds,
    # the rest is bad debt.
    sc.sweep("A11", "BUY", [("LIQ", 6)])
    assert st.accounts["A11"].free_cash < 0
    m = sc.find_mark("A11", lambda d, v: d > v + 5_000_000, 1_000_000, 90_000_000)
    reps = sc.do(crash(m), "chk_bad_debt_after_vault_is_empty")
    assert kinds(reps) == ["LIQUIDATED", "INSURANCE_DRAWN", "BAD_DEBT"], kinds(reps)
    assert st.fee_vault == 0 and st.accounts["A11"].free_cash < 0

    # chk2: a small deficit is paid by the fee vault alone
    sc.sweep("A12", "BUY", [("A1", 2), ("A3", 2), ("A2", 2), ("A10", 1)])
    m = sc.find_mark("A12", lambda d, v: v // 3 < d < v - 100_000, 1_000_000, 90_000_000)
    reps = sc.do(crash(m), "chk_vault_covers_whole_deficit")
    assert kinds(reps) == ["LIQUIDATED", "INSURANCE_DRAWN"], kinds(reps)
    assert st.accounts["A12"].free_cash == 0 and st.fee_vault > 0
    sc.flatten()

    # chk3: partial cover, then pro-rata sharing with leftover units. The weights are 3, 5, 3
    # (LIQ is short too but is never eligible). The leftover is 2: it goes to the heaviest
    # account and then, by the tie rule, to "A1" and not to "A10".
    # LIQ first takes a large short (A3 is long 20, the same side as the ruined account, so it is
    # not eligible). After the waterfall hands it the ruined long, LIQ is still short: it has the
    # opposite sign and would be charged if "LIQ" were not excluded by name.
    sc.do(nl("LIQ", "SELL", 20))
    sc.do(nl("A3", "BUY", 20))
    sc.sweep("A13", "BUY", [("A1", 3), ("A2", 5), ("A10", 3), ("LIQ", 2)])
    w = sc.weights("A13")
    assert w == {"A1": 3, "A2": 5, "A10": 3}, w
    assert st.accounts["LIQ"].position + 13 < 0

    def pred3(d, v):
        rem = d - min(d, v)
        return (rem > 50_000_000 and split(rem, w)[1] == 2
                and split(rem, w)[0] != split_largest_remainder(rem, w))

    m = sc.find_mark("A13", pred3, 1_000_000, 90_000_000)
    reps = sc.do(crash(m), "chk_loss_sharing_pro_rata_leftover_and_tie")
    adl = {r.account: r.qty for r in reps if r.kind == "ADL_APPLIED"}
    assert kinds(reps) == ["LIQUIDATED", "INSURANCE_DRAWN", "ADL_APPLIED", "ADL_APPLIED",
                           "ADL_APPLIED"], kinds(reps)
    assert [r.account for r in reps if r.kind == "ADL_APPLIED"] == ["A1", "A10", "A2"]
    assert adl["A1"] == adl["A10"] + 1 and "LIQ" not in adl
    sc.flatten()

    # chk4: three equal weights, one leftover unit: string order gives it to "A10"; the numeric
    # order would give it to "A2". The ADL reports are in string order too. (A LIQ maker keeps
    # the total weight different from the ruined position, so the remainder can take any value.)
    sc.sweep("A14", "BUY", [("A2", 2), ("A3", 2), ("A10", 2), ("LIQ", 1)])
    w = sc.weights("A14")

    def pred4(d, v):
        rem = d - min(d, v)
        return rem > 50_000_000 and split(rem, w)[1] == 1

    m = sc.find_mark("A14", pred4, 1_000_000, 90_000_000)
    reps = sc.do(crash(m), "chk_equal_weights_string_order_of_ids")
    assert [r.account for r in reps if r.kind == "ADL_APPLIED"] == ["A10", "A2", "A3"]
    adl = {r.account: r.qty for r in reps if r.kind == "ADL_APPLIED"}
    assert adl["A10"] == adl["A2"] + 1 == adl["A3"] + 1
    sc.flatten()

    # chk5: a short account is ruined by a price spike; the eligible accounts are the longs.
    # LIQ is long 20 first, so after it takes the ruined short it is still long (opposite sign).
    sc.do(nl("LIQ", "BUY", 20))
    sc.do(nl("A3", "SELL", 20))
    sc.sweep("A15", "SELL", [("A1", 2), ("A2", 2), ("A10", 3), ("LIQ", 1)])
    w = sc.weights("A15")
    assert w == {"A1": 2, "A2": 2, "A10": 3}, w
    assert st.accounts["LIQ"].position - 8 > 0

    def pred5(d, v):
        rem = d - min(d, v)
        return (rem > 50_000_000 and split(rem, w)[1] == 2
                and split(rem, w)[0] != split_largest_remainder(rem, w))

    m = sc.find_mark("A15", pred5, 150_000_000, 900_000_000)
    reps = sc.do(crash(m), "chk_short_account_loss_goes_to_longs")
    assert kinds(reps)[:2] == ["LIQUIDATED", "INSURANCE_DRAWN"]
    assert {r.account for r in reps if r.kind == "ADL_APPLIED"} == {"A1", "A2", "A10"}
    sc.flatten()

    # chk6: a liquidation that needs no bankruptcy: positive equity below the maintenance
    # requirement. Nothing is drawn, shared or reported besides LIQUIDATED.
    sc.sweep("A5", "SELL", [("A1", 3)])
    cash5 = st.accounts["A5"].free_cash
    lo = next(mk for mk in range(150_000_000, 900_000_000, 10_000)
              if cash5 - 3 * mk < (3 * mk * 500 + 9_999) // 10_000)
    assert cash5 - 3 * lo > 0
    vault_before = st.fee_vault
    reps = sc.do(crash(lo), "chk_liquidation_without_deficit")
    assert kinds(reps) == ["LIQUIDATED"] and st.fee_vault == vault_before
    sc.flatten()

    # chk7: loss sharing makes accounts insolvent in the middle of a sweep (rule R-L0). A 1%
    # margin rate allows 100x leverage. "A16" (long 36) is ruined; its counterparties "A4" (short
    # 31) and "A0" (short 5) hold almost no capital of their own, so after their loss share both
    # are below the maintenance requirement. "A4" is examined after "A16": it is liquidated in the
    # same event. "A0" was examined before "A16" and is not examined again: it keeps its position
    # until the next event. The same mark with PRICE_SHOCK would liquidate only "A16".
    sc.do(Event(kind="SET_MARGIN_RATE", bps=100))
    sc.sweep("A16", "BUY", [("A4", 31), ("A0", 5)])
    assert sc.weights("A16") == {"A4": 31, "A0": 5}

    def breach(eng, acc):
        a = eng.state.accounts[acc]
        req = (abs(a.position) * eng.state.mark_price * 500 + 9_999) // 10_000
        return a.position != 0 and a.free_cash + a.position * eng.state.mark_price < req

    found = None
    for mk in range(90_000_000, 1_000_000, -1_000):
        probe = copy.deepcopy(sc.eng)
        r_crash = probe.process(crash(mk))
        r_shock = copy.deepcopy(sc.eng).process(Event(kind="PRICE_SHOCK", mark_price=mk))
        liq_c = [r.account for r in r_crash if r.kind == "LIQUIDATED"]
        liq_s = [r.account for r in r_shock if r.kind == "LIQUIDATED"]
        if (liq_c == ["A16", "A4"] and liq_s == ["A16"] and breach(probe, "A0")
                and "BAD_DEBT" not in kinds(r_crash)):
            found = mk
            break
    assert found is not None, "no cascading mark found"
    reps = sc.do(crash(found), "chk_loss_share_makes_accounts_insolvent_mid_sweep")
    ks = kinds(reps)
    assert ks.count("LIQUIDATED") == 2 and st.accounts["A0"].position == -5, ks
    # the next event examines "A0" and liquidates it
    reps = sc.do(crash(found), "chk_earlier_account_is_examined_in_the_next_event")
    assert kinds(reps) == ["LIQUIDATED"] and reps[1].account == "A0"
    sc.do(Event(kind="SET_MARGIN_RATE", bps=2000))

    # chk8 to chk10: the fee vault can be negative (a funding residual, R-Y3). Insurance never
    # draws on a negative vault (R-L2 caps the draw at max(0, vault)).
    # Setup: "A6" (thin) buys 6 from three pool accounts; "A10" buys 6 from the thin short "A8".
    sc.flatten()
    sc.sweep("A6", "BUY", [("A1", 2), ("A2", 2), ("A3", 2)])
    sc.sweep("A10", "BUY", [("A8", 6)])
    assert st.accounts["A8"].position == -6 and st.accounts["A10"].position == 6
    m1 = sc.find_mark("A6", lambda d, v: d > v + 5_000_000, 1_000_000, 90_000_000)
    reps = sc.do(crash(m1), "chk_crash_drains_the_fee_vault")
    assert kinds(reps)[:3] == ["LIQUIDATED", "INSURANCE_DRAWN", "ADL_APPLIED"], kinds(reps)
    assert st.fee_vault == 0

    # A funding event whose per-account rounding pays out more than it collects: with an empty
    # vault the residual leaves it below zero. The rate is searched.
    rate = next(r for r in list(range(1, 400)) + list(range(-399, 0))
                if _vault_after_funding(sc.eng, r) < 0)
    sc.do(Event(kind="FUNDING", bps=rate), "chk_funding_residual_makes_the_vault_negative")
    assert st.fee_vault < 0, st.fee_vault

    # "A8" (short 6, thin) is ruined by a price spike. The vault is negative, so no insurance is
    # drawn and the WHOLE deficit is shared; the vault stays as it is. The only eligible account
    # is the long "A10" (LIQ is never eligible).
    vault_neg = st.fee_vault
    m2 = sc.find_mark("A8", lambda d, v: d > 5_000_000, 160_000_000, 900_000_000)
    deficit8 = sc.deficit_at("A8", m2)
    reps = sc.do(crash(m2), "chk_negative_vault_is_not_insurance")
    adl = [r for r in reps if r.kind == "ADL_APPLIED"]
    assert kinds(reps) == ["LIQUIDATED", "ADL_APPLIED"], kinds(reps)
    assert adl[0].account == "A10" and adl[0].qty == deficit8
    assert st.fee_vault == vault_neg
    sc.flatten()

    # chk11: the remainder after the insurance draw is 2, smaller than the number of eligible
    # accounts. Weights 1, 4, 1: the shares are 0, 2, 0 (the leftover goes to the heaviest). Only
    # accounts with share > 0 get an ADL_APPLIED report (R-L3), and no other report appears
    # (exact_reports). The initial cash of "A7" is adjusted (see NeedAdjust) so that a mark exists
    # at which the deficit exceeds the vault by exactly 2.
    sc.sweep("A7", "BUY", [("A1", 1), ("A2", 4), ("A3", 1)])
    a7 = st.accounts["A7"]
    adj = (-a7.free_cash - st.fee_vault - 2) % 6
    if adj:
        raise NeedAdjust(adj)
    m3 = (-a7.free_cash - st.fee_vault - 2) // 6
    assert sc.deficit_at("A7", m3) - st.fee_vault == 2
    w = sc.weights("A7")
    assert w == {"A1": 1, "A2": 4, "A3": 1}, w
    assert 0 in split(2, w)[0].values()
    reps = sc.do(crash(m3), "chk_zero_share_is_not_reported", exact=True)
    assert kinds(reps) == ["LIQUIDATED", "INSURANCE_DRAWN", "ADL_APPLIED"], kinds(reps)
    assert [(r.account, r.qty) for r in reps if r.kind == "ADL_APPLIED"] == [("A2", 2)]
    assert st.fee_vault == 0

    return sc


def write(sc: Scenario) -> Path:
    out = {"accounts": ACCOUNTS, "mark_price": P, "events": sc.events,
           "checkpoints": sc.checkpoints}
    path = REPO_ROOT / "tasks" / "f8_adl_b" / "tier2_trace.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return path


def build() -> Scenario:
    """main(), run again with a changed initial cash for "A7" if the scenario asks for it."""
    try:
        return main()
    except NeedAdjust as need:
        ACCOUNTS["A7"] += need.adj
        return main()


if __name__ == "__main__":
    scenario = build()
    path = write(scenario)
    print(f"wrote {path} ({len(scenario.events)} events, {len(scenario.checkpoints)} checkpoints)")
    for cp in scenario.checkpoints:
        reps = [(r["kind"], r.get("account"), r.get("qty")) for r in cp["expected_reports"]
                if r["kind"] != "MARK_SET"]
        print(f"  {cp['name']}: {reps}")
