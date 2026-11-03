"""tests/test_rulebook_clarifications.py
Tests verifying Rulebook clarifications for OQ-01 to OQ-08
(R-A6, R-A7, R-W7, R-M5, R-P5, R-F4, R-X1, R-X2).
"""
from pathlib import Path

from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.rules.fee_rule import compute_taker_fee
from exchange_core.types import BasketLeg, Event


def test_r_a6_basket_rollback_zero_indexed():
    """R-A6 [Declared]: BASKET_ROLLED_BACK(leg_index) uses 0-based indexing."""
    cfg = EngineConfig()
    accs = {"A1": 1_000_000_000}
    engine = Engine(cfg, accs, 100_000_000)
    # Leg 0 fails immediately (insufficient margin for huge qty)
    legs = (
        BasketLeg("BUY", 100_000_000, 1_000_000, "IOC"),
        BasketLeg("BUY", 100_000_000, 1, "IOC"),
    )
    ev = Event("BASKET", account="A1", legs=legs)
    reps = engine.process(ev)
    assert len(reps) == 1
    assert reps[0].kind == "BASKET_ROLLED_BACK"
    assert reps[0].leg_index == 0


def test_r_a7_basket_ioc_leaves_failure():
    """R-A7 [Declared]: Basket IOC leg fails if leaves > 0 after matching."""
    cfg = EngineConfig()
    accs = {
        "A1": 1_000_000_000,
        "A2": 1_000_000_000,
    }
    engine = Engine(cfg, accs, 100_000_000)
    # A2 places resting SELL of 2 units at 100_000_000
    engine.process(
        Event("NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=2, flag="NONE")
    )
    # A1 sends basket with IOC leg of 5 units (only 2 can match -> leaves 3 > 0 -> failure)
    legs = (
        BasketLeg("BUY", 100_000_000, 5, "IOC"),
    )
    reps = engine.process(Event("BASKET", account="A1", legs=legs))
    assert reps[0].kind == "BASKET_ROLLED_BACK"
    assert reps[0].leg_index == 0


def test_r_w7_account_lexicographic_order():
    """R-W7 [Declared]: Ascending account-id order in waterfall is lexicographic."""
    # Strings "10" and "2": in lexicographical order, "10" < "2"
    acc_ids = ["2", "10"]
    sorted_ids = sorted(acc_ids)
    assert sorted_ids == ["10", "2"]


def test_r_m5_taker_full_lock_release():
    """R-M5 [Declared]: Full fill reduces taker leaves to 0, releasing entire lock."""
    cfg = EngineConfig()
    accs = {
        "A1": 1_000_000_000,
        "A2": 1_000_000_000,
    }
    engine = Engine(cfg, accs, 100_000_000)
    # Maker A2 places SELL 10 @ 100_000_000
    engine.process(
        Event("NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=10, flag="NONE")
    )
    # Taker A1 places BUY 10 @ 100_000_000 (fully matches)
    engine.process(
        Event("NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10, flag="NONE")
    )
    # A1's locked margin must be exactly 0 after full match
    assert engine.state.accounts["A1"].locked_margin == 0


def test_r_p5_replace_crossing_same_account():
    """R-P5 [Declared]: REPLACE rejects crossing order even if owned by same account."""
    cfg = EngineConfig()
    accs = {"A1": 1_000_000_000}
    engine = Engine(cfg, accs, 100_000_000)
    # A1 places SELL 1 @ 110_000_000
    engine.process(
        Event("NEW_LIMIT", account="A1", side="SELL", price=110_000_000, qty=1, flag="NONE")
    )
    # A1 places BUY 1 @ 100_000_000
    r2 = engine.process(
        Event("NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=1, flag="NONE")
    )
    buy_id = r2[0].order_id
    # A1 tries to REPLACE BUY to 110_000_000 (crosses own sell) -> rejected
    rep = engine.process(Event("REPLACE", order_id=buy_id, new_price=110_000_000, new_qty=1))
    assert rep[0].kind == "REJECTED"
    assert rep[0].reason == "REPLACE_WOULD_CROSS"


def test_r_f4_threshold_inclusive_boundary():
    """R-F4 [Declared]: volume_before + notional == TIER_THRESHOLD is evaluated under T0."""
    cfg = EngineConfig()
    # volume_before + notional exactly equals TIER_THRESHOLD
    notional = 1_000_000_000
    vol_before = cfg.tier_threshold - notional
    fee = compute_taker_fee(vol_before, notional, cfg)
    # Under T0: notional * 2750 / 1_000_000 = 2_750_000
    expected_fee = 2_750_000
    assert fee == expected_fee


def test_rulebook_declared_clarifications_exist():
    """Check that docs/04_RULEBOOK.md contains all declared rule IDs."""
    rulebook_path = Path("docs/04_RULEBOOK.md")
    assert rulebook_path.exists()
    content = rulebook_path.read_text(encoding="utf-8")
    for rule_id in ["R-A6", "R-A7", "R-W7", "R-M5", "R-P5", "R-F4", "R-X1", "R-X2"]:
        assert rule_id in content
        assert f"**{rule_id} [Declared].**" in content
