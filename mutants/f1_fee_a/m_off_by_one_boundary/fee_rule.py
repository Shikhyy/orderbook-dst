"""mutants/f1_fee_a/m_off_by_one_boundary/fee_rule.py
Mutant with off-by-one boundary check (< instead of <=).
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    if volume_before >= cfg.tier_threshold:
        return round_half_even(notional * cfg.taker_ppm_t1, cfg.ppm)
    # Mutant bug: strict inequality < instead of <= and shifted boundary
    if volume_before + notional < cfg.tier_threshold:
        return round_half_even(notional * cfg.taker_ppm_t0, cfg.ppm)
    below = (cfg.tier_threshold - cfg.tick) - volume_before
    if below < 0:
        below = 0
    above = notional - below
    fee_below = round_half_even(below * cfg.taker_ppm_t0, cfg.ppm)
    fee_above = round_half_even(above * cfg.taker_ppm_t1, cfg.ppm)
    return fee_below + fee_above


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)
