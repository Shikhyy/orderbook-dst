"""exchange_core/rules/fee_rule.py
Pure functions for taker fee and maker rebate calculation.
Rules R-F2 and R-F3. Target for task f1_fee_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic (Rule R-F2)."""
    ppm = cfg.PPM
    t0 = cfg.TAKER_PPM_T0
    t1 = cfg.TAKER_PPM_T1
    threshold = cfg.TIER_THRESHOLD

    if volume_before >= threshold:
        # Rule R-F2: If volume_before >= TIER_THRESHOLD
        return round_half_even(notional * t1, ppm)

    if volume_before + notional <= threshold:
        # Rule R-F2: If volume_before + notional <= TIER_THRESHOLD
        return round_half_even(notional * t0, ppm)

    # Rule R-F2: Otherwise the fill crosses the threshold. Split it.
    below = threshold - volume_before
    above = notional - below
    fee_below = round_half_even(below * t0, ppm)
    fee_above = round_half_even(above * t1, ppm)
    return fee_below + fee_above


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill (Rule R-F3)."""
    ppm = cfg.PPM
    rebate_ppm = cfg.MAKER_REBATE_PPM
    return round_half_even(notional * rebate_ppm, ppm)
