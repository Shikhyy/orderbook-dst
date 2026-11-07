"""exchange_core/rules/fee_rule.py
Pure functions for taker fee and maker rebate calculation.
Rules R-F2 and R-F3. Target for task f1_fee_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic (Rule R-F2)."""
    threshold = cfg.tier_threshold
    ppm = cfg.ppm
    t0 = cfg.taker_ppm_t0
    t1 = cfg.taker_ppm_t1

    if volume_before >= threshold:
        # Entire fill at T1 rate
        return round_half_even(notional * t1, ppm)
    elif volume_before + notional <= threshold:
        # Entire fill at T0 rate
        return round_half_even(notional * t0, ppm)
    else:
        # Fill crosses the threshold
        below = threshold - volume_before
        above = notional - below
        fee_below = round_half_even(below * t0, ppm)
        fee_above = round_half_even(above * t1, ppm)
        return fee_below + fee_above


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill (Rule R-F3)."""
    return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)
