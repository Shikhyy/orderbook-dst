"""tasks/f2_replace_a/public_tests/test_f2_replace_a.py
Public unit tests for decide_replace (Rule R-P1, R-P2 steps 2-3, R-P3).
"""
import pytest

from exchange_core.config import EngineConfig
from exchange_core.rules.replace_rule import decide_replace
from exchange_core.types import Order


@pytest.fixture
def cfg() -> EngineConfig:
    return EngineConfig()


def make_order(
    order_id: int = 1,
    account: str = "A1",
    side: str = "BUY",
    price: int = 100_000_000,
    qty: int = 10,
    cum_qty: int = 0,
    prio_seq: int = 1,
) -> Order:
    return Order(
        order_id=order_id,
        account=account,
        side=side,
        price=price,
        qty=qty,
        cum_qty=cum_qty,
        prio_seq=prio_seq,
        margin_bps=2000,
        lock=200_000_000,
    )


def test_1_decrease_keeps_priority(cfg: EngineConfig) -> None:
    order = make_order(qty=10, cum_qty=0)
    decision = decide_replace(order, new_price=100_000_000, new_qty=8, cfg=cfg)
    assert decision.ok is True
    assert decision.reason == ""
    assert decision.keep_priority is True
    assert decision.new_leaves == 8


def test_2_increase_loses_priority(cfg: EngineConfig) -> None:
    order = make_order(qty=10, cum_qty=0)
    decision = decide_replace(order, new_price=100_000_000, new_qty=12, cfg=cfg)
    assert decision.ok is True
    assert decision.reason == ""
    assert decision.keep_priority is False
    assert decision.new_leaves == 12


def test_3_price_change_loses_priority(cfg: EngineConfig) -> None:
    order = make_order(qty=10, cum_qty=0)
    decision = decide_replace(order, new_price=101_000_000, new_qty=8, cfg=cfg)
    assert decision.ok is True
    assert decision.reason == ""
    assert decision.keep_priority is False
    assert decision.new_leaves == 8


def test_4_same_qty_and_price_noop(cfg: EngineConfig) -> None:
    order = make_order(qty=10, cum_qty=0)
    decision = decide_replace(order, new_price=100_000_000, new_qty=10, cfg=cfg)
    assert decision.ok is True
    assert decision.reason == ""
    assert decision.keep_priority is True
    assert decision.new_leaves == 10


def test_5_new_qty_equal_to_cum_qty_rejected(cfg: EngineConfig) -> None:
    order = make_order(qty=10, cum_qty=4)
    decision = decide_replace(order, new_price=100_000_000, new_qty=4, cfg=cfg)
    assert decision.ok is False
    assert decision.reason == "INVALID_REPLACE"
    assert decision.new_leaves == 0


def test_6_new_qty_below_cum_qty_rejected(cfg: EngineConfig) -> None:
    order = make_order(qty=10, cum_qty=4)
    decision = decide_replace(order, new_price=100_000_000, new_qty=3, cfg=cfg)
    assert decision.ok is False
    assert decision.reason == "INVALID_REPLACE"
    assert decision.new_leaves == 0


def test_7_invalid_price(cfg: EngineConfig) -> None:
    order = make_order(qty=10, cum_qty=0)
    # Zero price
    d1 = decide_replace(order, new_price=0, new_qty=8, cfg=cfg)
    assert d1.ok is False
    assert d1.reason == "INVALID_ORDER"

    # Non-tick price (tick is 10,000)
    d2 = decide_replace(order, new_price=100_005_000, new_qty=8, cfg=cfg)
    assert d2.ok is False
    assert d2.reason == "INVALID_ORDER"


def test_8_partial_fill_case(cfg: EngineConfig) -> None:
    order = make_order(qty=10, cum_qty=4)
    # Decrease from 10 to 7 (leaves goes from 6 to 3)
    decision = decide_replace(order, new_price=100_000_000, new_qty=7, cfg=cfg)
    assert decision.ok is True
    assert decision.reason == ""
    assert decision.keep_priority is True
    assert decision.new_leaves == 3


def test_9_large_quantity(cfg: EngineConfig) -> None:
    order = make_order(qty=1_000_000, cum_qty=500_000)
    decision = decide_replace(order, new_price=100_000_000, new_qty=2_000_000, cfg=cfg)
    assert decision.ok is True
    assert decision.reason == ""
    assert decision.keep_priority is False
    assert decision.new_leaves == 1_500_000
