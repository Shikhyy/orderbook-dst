"""tasks/f1_fee_a/public_tests/test_f1_fee_a.py
Public tests for task f1_fee_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.rules.fee_rule import compute_maker_rebate, compute_taker_fee


def test_below_threshold():
    cfg = EngineConfig()
    vol_before = 1_000_000_000
    notional = 2_000_000_000
    fee = compute_taker_fee(vol_before, notional, cfg)
    assert fee == 5_500_000
    rebate = compute_maker_rebate(notional, cfg)
    assert rebate == 500_000


def test_above_threshold():
    cfg = EngineConfig()
    vol_before = 6_000_000_000
    notional = 2_000_000_000
    fee = compute_taker_fee(vol_before, notional, cfg)
    assert fee == 3_700_000


def test_fill_ends_exactly_on_threshold():
    cfg = EngineConfig()
    vol_before = 3_000_010_000
    notional = 2_000_000_000
    # Sum is 5_000_010_000 == cfg.tier_threshold
    fee = compute_taker_fee(vol_before, notional, cfg)
    assert fee == 5_500_000


def test_volume_before_equals_threshold():
    cfg = EngineConfig()
    vol_before = cfg.tier_threshold
    notional = 2_000_000_000
    fee = compute_taker_fee(vol_before, notional, cfg)
    assert fee == 3_700_000


def test_crossing_fill():
    cfg = EngineConfig()
    vol_before = 4_000_010_000
    notional = 2_000_000_000
    # below = 1_000_000_000 @ T0 (2750 ppm) = 2_750_000
    # above = 1_000_000_000 @ T1 (1850 ppm) = 1_850_000
    # total fee = 4_600_000
    fee = compute_taker_fee(vol_before, notional, cfg)
    assert fee == 4_600_000


def test_tie_rounding_down():
    cfg = EngineConfig()
    # 6000 * 2750 = 16_500_000 / 1_000_000 = 16.5 -> 16 (even)
    fee = compute_taker_fee(0, 6000, cfg)
    assert fee == 16


def test_tie_rounding_up():
    cfg = EngineConfig()
    # 2000 * 2750 = 5_500_000 / 1_000_000 = 5.5 -> 6 (even)
    fee = compute_taker_fee(0, 2000, cfg)
    assert fee == 6


def test_zero_volume_start():
    cfg = EngineConfig()
    vol_before = 0
    notional = 1_000_000_000
    fee = compute_taker_fee(vol_before, notional, cfg)
    assert fee == 2_750_000
    rebate = compute_maker_rebate(notional, cfg)
    assert rebate == 250_000
