"""exchange_core/rules/fee_rule.py
Pure fee calculation rules R-F1, R-F2, R-F3.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill.

    Rule R-F2:
    - If volume_before >= TIER_THRESHOLD:
        fee = round_half_even(notional * TAKER_PPM_T1, PPM)
    - If volume_before + notional <= TIER_THRESHOLD:
        fee = round_half_even(notional * TAKER_PPM_T0, PPM)
    - Otherwise split at threshold:
        below = TIER_THRESHOLD - volume_before
        above = notional - below
        fee = (round_half_even(below * TAKER_PPM_T0, PPM) +
               round_half_even(above * TAKER_PPM_T1, PPM))
    """
    if notional <= 0:
        return 0
    if volume_before >= cfg.tier_threshold:
        return round_half_even(notional * cfg.taker_ppm_t1, cfg.ppm)
    if volume_before + notional <= cfg.tier_threshold:
        return round_half_even(notional * cfg.taker_ppm_t0, cfg.ppm)

    below = cfg.tier_threshold - volume_before
    above = notional - below
    fee_below = round_half_even(below * cfg.taker_ppm_t0, cfg.ppm)
    fee_above = round_half_even(above * cfg.taker_ppm_t1, cfg.ppm)
    return fee_below + fee_above


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill.

    Rule R-F3:
    rebate = round_half_even(notional * MAKER_REBATE_PPM, PPM)
    """
    if notional <= 0:
        return 0
    return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)
