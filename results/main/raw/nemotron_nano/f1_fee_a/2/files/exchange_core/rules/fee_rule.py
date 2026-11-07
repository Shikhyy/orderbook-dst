"""exchange_core/rules/fee_rule.py
Pure functions for taker fee and maker rebate calculation.
Rules R-F2 and R-F3. Target for task f1_fee_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic (Rule R-F2)."""
    T0 = cfg.TAKER_PPM_T0
    T1 = cfg.TAKER_PPM_T1
    PPM = cfg.PPM
    TIER = cfg.TIER_THRESHOLD

    if volume_before >= TIER:
        # All above threshold
        fee = round_half_even(notional * T1, PPM)
    elif volume_before + notional <= TIER:
        # All below threshold
        fee = round_half_even(notional * T0, PPM)
    else:
        # Crossing the threshold
        below = TIER - volume_before
        above = notional - below
        fee = round_half_even(below * T0, PPM) + round_half_even(above * T1, PPM)

    return fee


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill (Rule R-F3)."""
    MAKER_REBATE_PPM = cfg.MAKER_REBATE_PPM
    PPM = cfg.PPM
    return round_half_even(notional * MAKER_REBATE_PPM, PPM)
