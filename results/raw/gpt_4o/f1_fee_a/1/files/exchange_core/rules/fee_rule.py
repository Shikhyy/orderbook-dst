"""Fee calculation rules (Task f1_fee_a).

Rules:
- R-F1: Volume tracking.
- R-F2: Taker fee calculation with tier threshold splitting.
- R-F3: Maker rebate calculation.
- R-F4: Fee threshold inclusive boundary.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute taker fee in micro-USD.

    Rules R-F2, R-F4:
    - If volume_before >= cfg.tier_threshold:
        fee = round_half_even(notional * cfg.taker_ppm_t1, cfg.ppm)
    - If volume_before + notional <= cfg.tier_threshold:
        fee = round_half_even(notional * cfg.taker_ppm_t0, cfg.ppm)
    - Otherwise (crosses the threshold):
        below = cfg.tier_threshold - volume_before
        above = notional - below
        fee = (
            round_half_even(below * cfg.taker_ppm_t0, cfg.ppm)
            + round_half_even(above * cfg.taker_ppm_t1, cfg.ppm)
        )
    """
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
    """Compute maker rebate in micro-USD.

    Rule R-F3:
    rebate = round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)
    """
    return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)
