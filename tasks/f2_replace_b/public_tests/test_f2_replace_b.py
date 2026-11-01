"""tasks/f2_replace_b/public_tests/test_f2_replace_b.py
Public unit tests for handle_replace (Rules R-P1 to R-P4, R-U3).
"""
import pytest

from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.handlers.replace import handle_replace
from exchange_core.types import Event


@pytest.fixture
def cfg() -> EngineConfig:
    return EngineConfig()


@pytest.fixture
def engine(cfg: EngineConfig) -> Engine:
    accounts = {
        "A1": 1_000_000_000,
        "A2": 1_000_000_000,
        "A3": 1_000_000_000,
    }
    return Engine(cfg, accounts, 100_000_000)


def test_1_decrease_keeps_priority(engine: Engine) -> None:
    # A1 places BUY qty=10 at 100M
    engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    # Replace to qty=8, same price
    ev = Event(kind="REPLACE", order_id=1, new_price=100_000_000, new_qty=8)
    reps = handle_replace(engine, ev)
    assert [r.kind for r in reps] == ["REPLACED"]
    assert reps[0].order_id == 1
    assert engine.state.orders[1].prio_seq == 1
    assert engine.state.orders[1].leaves == 8


def test_2_increase_loses_priority(engine: Engine) -> None:
    engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    prio_before = engine.state.orders[1].prio_seq
    ev = Event(kind="REPLACE", order_id=1, new_price=100_000_000, new_qty=12)
    reps = handle_replace(engine, ev)
    assert [r.kind for r in reps] == ["REPLACED"]
    assert engine.state.orders[1].prio_seq > prio_before
    assert engine.state.orders[1].leaves == 12


def test_3_price_change_loses_priority(engine: Engine) -> None:
    engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    prio_before = engine.state.orders[1].prio_seq
    ev = Event(kind="REPLACE", order_id=1, new_price=99_000_000, new_qty=8)
    reps = handle_replace(engine, ev)
    assert [r.kind for r in reps] == ["REPLACED"]
    assert engine.state.orders[1].prio_seq > prio_before
    assert engine.state.orders[1].price == 99_000_000


def test_4_same_qty_and_price_noop(engine: Engine) -> None:
    engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    prio_before = engine.state.orders[1].prio_seq
    ev = Event(kind="REPLACE", order_id=1, new_price=100_000_000, new_qty=10)
    reps = handle_replace(engine, ev)
    assert [r.kind for r in reps] == ["REPLACED"]
    assert engine.state.orders[1].prio_seq == prio_before
    assert engine.state.orders[1].leaves == 10


def test_5_new_qty_equal_to_cum_qty_rejected(engine: Engine) -> None:
    engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    # A2 sells 4, filling 4 of order 1
    engine.process(Event(kind="NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=4))
    assert engine.state.orders[1].cum_qty == 4

    ev = Event(kind="REPLACE", order_id=1, new_price=100_000_000, new_qty=4)
    reps = handle_replace(engine, ev)
    assert [r.kind for r in reps] == ["REJECTED"]
    assert reps[0].reason == "INVALID_REPLACE"
    assert engine.state.orders[1].leaves == 6


def test_6_new_qty_below_cum_qty_rejected(engine: Engine) -> None:
    engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    engine.process(Event(kind="NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=4))
    ev = Event(kind="REPLACE", order_id=1, new_price=100_000_000, new_qty=3)
    reps = handle_replace(engine, ev)
    assert [r.kind for r in reps] == ["REJECTED"]
    assert reps[0].reason == "INVALID_REPLACE"


def test_7_invalid_price(engine: Engine) -> None:
    engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    # Zero price
    r1 = handle_replace(engine, Event(kind="REPLACE", order_id=1, new_price=0, new_qty=8))
    assert [r.kind for r in r1] == ["REJECTED"]
    assert r1[0].reason == "INVALID_ORDER"

    # Non-tick price (100_005_000 % 10_000 != 0)
    ev = Event(kind="REPLACE", order_id=1, new_price=100_005_000, new_qty=8)
    r2 = handle_replace(engine, ev)
    assert [r.kind for r in r2] == ["REJECTED"]
    assert r2[0].reason == "INVALID_ORDER"


def test_8_partial_fill_case(engine: Engine) -> None:
    engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    engine.process(Event(kind="NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=4))
    prio_before = engine.state.orders[1].prio_seq

    # Decrease total qty from 10 to 7 (cum_qty is 4, new leaves is 3)
    ev = Event(kind="REPLACE", order_id=1, new_price=100_000_000, new_qty=7)
    reps = handle_replace(engine, ev)
    assert [r.kind for r in reps] == ["REPLACED"]
    assert engine.state.orders[1].prio_seq == prio_before
    assert engine.state.orders[1].leaves == 3


def test_9_large_quantity(engine: Engine) -> None:
    # A1 places order with 10 lots
    engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    # Replace to 20 lots
    ev = Event(kind="REPLACE", order_id=1, new_price=100_000_000, new_qty=20)
    reps = handle_replace(engine, ev)
    assert [r.kind for r in reps] == ["REPLACED"]
    assert engine.state.orders[1].leaves == 20


def test_10_lock_change_and_cash_adjustment(engine: Engine) -> None:
    # A1 initial: free_cash = 1_000_000_000, locked = 0
    engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    # Lock for 10 lots @ 100M, rate 20% (2000 bps) = 200_000_000
    assert engine.state.accounts["A1"].free_cash == 800_000_000
    assert engine.state.accounts["A1"].locked_margin == 200_000_000

    # Replace to qty=6 (lock becomes 120_000_000)
    ev = Event(kind="REPLACE", order_id=1, new_price=100_000_000, new_qty=6)
    handle_replace(engine, ev)
    assert engine.state.accounts["A1"].free_cash == 880_000_000
    assert engine.state.accounts["A1"].locked_margin == 120_000_000
    assert engine.state.orders[1].lock == 120_000_000

    # Replace that requires more margin than free cash must be rejected
    ev_huge = Event(kind="REPLACE", order_id=1, new_price=1_000_000_000, new_qty=60)
    r = handle_replace(engine, ev_huge)
    assert [rep.kind for rep in r] == ["REJECTED"]
    assert r[0].reason == "INSUFFICIENT_MARGIN"
    # State remains untouched
    assert engine.state.accounts["A1"].free_cash == 880_000_000
    assert engine.state.accounts["A1"].locked_margin == 120_000_000
