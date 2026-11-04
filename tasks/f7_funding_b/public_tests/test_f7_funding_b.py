"""tasks/f7_funding_b/public_tests/test_f7_funding_b.py
Public unit tests for task f7_funding_b.
"""
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.types import Event

P = 100_000_000


def make():
    accounts = {"A1": 5_000_000_000, "A2": 5_000_000_000, "LIQ": 50_000_000_000}
    return Engine(EngineConfig(), accounts, mark_price=P)


def trade(eng, qty):
    """A1 sells qty to A2 at P: A1 is short, A2 is long."""
    eng.process(Event(kind="NEW_LIMIT", account="A1", side="SELL", price=P, qty=qty))
    eng.process(Event(kind="NEW_LIMIT", account="A2", side="BUY", price=P, qty=qty))


def cash(eng):
    return {a: v.free_cash for a, v in eng.state.accounts.items()}


def test_no_positions_only_reports():
    eng = make()
    reps = eng.process(Event(kind="FUNDING", bps=1000))
    assert [r.kind for r in reps] == ["FUNDING_APPLIED", "MARK_SET"]
    assert reps[0].bps == 1000 and reps[0].qty == 0
    assert reps[1].mark_price == P


def test_positive_rate_long_pays_short():
    eng = make()
    trade(eng, 3)
    before, vault = cash(eng), eng.state.fee_vault
    reps = eng.process(Event(kind="FUNDING", bps=1000))
    amount = 3 * P * 1000 // 1_000_000
    after = cash(eng)
    assert after["A2"] == before["A2"] - amount
    assert after["A1"] == before["A1"] + amount
    assert after["LIQ"] == before["LIQ"]
    assert eng.state.fee_vault == vault
    assert reps[0].kind == "FUNDING_APPLIED" and reps[0].qty == 2


def test_negative_rate_short_pays_long():
    eng = make()
    trade(eng, 2)
    before = cash(eng)
    eng.process(Event(kind="FUNDING", bps=-500))
    amount = 2 * P * 500 // 1_000_000
    after = cash(eng)
    assert after["A1"] == before["A1"] - amount
    assert after["A2"] == before["A2"] + amount


def test_rate_is_clamped():
    eng = make()
    trade(eng, 1)
    before = cash(eng)
    reps = eng.process(Event(kind="FUNDING", bps=9000))
    assert reps[0].bps == 3000
    assert before["A2"] - cash(eng)["A2"] == P * 3000 // 1_000_000
