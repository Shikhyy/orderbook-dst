"""tasks/f6_match_b/public_tests/test_f6_match_b.py
Public unit tests for task f6_match_b.
"""
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.types import Event, Report

P = 100_000_000


def make(accounts=None):
    accounts = accounts or {"A1": 2_000_000_000, "A2": 2_000_000_000, "LIQ": 10_000_000_000}
    return Engine(EngineConfig(), accounts, mark_price=P)


def new(eng, acc, side, price, qty, flag="NONE"):
    return eng.process(
        Event(kind="NEW_LIMIT", account=acc, side=side, price=price, qty=qty, flag=flag)
    )


def test_resting_order_locks_margin():
    eng = make()
    reps = new(eng, "A1", "BUY", P, 3)
    assert reps == [Report.accepted(1)]
    acc = eng.state.accounts["A1"]
    assert acc.locked_margin == 3 * P * 2000 // 10000
    assert acc.free_cash == 2_000_000_000 - acc.locked_margin
    assert 1 in eng.state.orders and eng.state.next_order_id == 2


def test_validation_rejects_change_nothing():
    eng = make()
    h = eng.state_hash()
    assert new(eng, "NOPE", "BUY", P, 1) == [Report.rejected("UNKNOWN_ACCOUNT")]
    assert new(eng, "A1", "BUY", P + 5, 1) == [Report.rejected("INVALID_ORDER")]
    assert new(eng, "A1", "BUY", P, 0) == [Report.rejected("INVALID_ORDER")]
    assert eng.state_hash() == h


def test_insufficient_margin_is_rejected():
    eng = make({"A1": 10_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000})
    assert new(eng, "A1", "BUY", P, 1) == [Report.rejected("INSUFFICIENT_MARGIN")]
    assert eng.state.next_order_id == 1


def test_full_cross_fills_at_resting_price():
    eng = make()
    new(eng, "A2", "SELL", P, 2)
    reps = new(eng, "A1", "BUY", P + 10_000, 2)
    assert reps[0] == Report.accepted(2)
    assert reps[1] == Report.fill(2, 1, P, 2, 2)
    assert len(reps) == 2
    assert eng.state.accounts["A1"].position == 2
    assert eng.state.accounts["A2"].position == -2
    assert eng.state.accounts["A1"].locked_margin == 0
    assert eng.state.accounts["A2"].locked_margin == 0
    assert eng.state.orders == {}


def test_partial_fill_rests_remainder():
    eng = make()
    new(eng, "A2", "SELL", P, 2)
    reps = new(eng, "A1", "BUY", P, 5)
    assert reps == [Report.accepted(2), Report.fill(2, 1, P, 2, 2)]
    rest = eng.state.orders[2]
    assert rest.cum_qty == 2 and rest.leaves == 3
    assert rest.lock == 3 * P * 2000 // 10000
    assert eng.state.accounts["A1"].locked_margin == rest.lock


def test_ioc_remainder_is_cancelled_and_not_stored():
    eng = make()
    new(eng, "A2", "SELL", P, 1)
    reps = new(eng, "A1", "BUY", P, 4, flag="IOC")
    assert reps == [
        Report.accepted(2),
        Report.fill(2, 1, P, 1, 2),
        Report.cancelled(2, "IOC_REMAINDER"),
    ]
    assert eng.state.orders == {}
    assert eng.state.accounts["A1"].locked_margin == 0


def test_post_only_that_would_cross_is_rejected():
    eng = make()
    new(eng, "A2", "SELL", P, 2)
    h = eng.state_hash()
    assert new(eng, "A1", "BUY", P, 1, flag="POST_ONLY") == [
        Report.rejected("POST_ONLY_WOULD_CROSS")
    ]
    assert eng.state_hash() == h


def test_self_trade_cancels_resting_order():
    eng = make()
    new(eng, "A1", "SELL", P, 2)
    reps = new(eng, "A1", "BUY", P, 1)
    assert reps == [Report.accepted(2), Report.cancelled(1, "STP")]
    assert 1 not in eng.state.orders and 2 in eng.state.orders
    assert eng.state.accounts["A1"].locked_margin == P * 2000 // 10000
