"""exchange_core/rules/fee_rule.py
Pure functions for taker fee and maker rebate calculation.
Rules R-F2 and R-F3. Target for task f1_fee_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic (Rule R-F2)."""
    threshold = cfg.TIER_THRESHOLD
    
    if volume_before >= threshold:
        # Tier 1 applied to the full notional
        return round_half_even(notional * cfg.TAKER_PPM_T1, cfg.PPM)
    
    if volume_before + notional <= threshold:
        # Tier 0 applied to the full notional
        return round_half_even(notional * cfg.TAKER_PPM_T0, cfg.PPM)
    
    # Fill crosses the threshold
    below = threshold - volume_before
    above = notional - below
    
    fee_below = round_half_even(below * cfg.TAKER_PPM_T0, cfg.PPM)
    fee_above = round_half_even(above * cfg.TAKER_PPM_T1, cfg.PPM)
    
    return fee_below + fee_above


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill (Rule R-F3)."""
    return round_half_even(notional * cfg.MAKER_REBATE_PPM, cfg.PPM)
