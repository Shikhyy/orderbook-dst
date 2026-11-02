"""mutants/f1_fee_a/m_round_half_up/fee_rule.py
Mutant that uses round-half-up instead of round-half-even.
"""
from exchange_core.config import EngineConfig


def _round_half_up(n: int, d: int) -> int:
    return (2 * n + d) // (2 * d)


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    if volume_before >= cfg.tier_threshold:
        return _round_half_up(notional * cfg.taker_ppm_t1, cfg.ppm)
    if volume_before + notional <= cfg.tier_threshold:
        return _round_half_up(notional * cfg.taker_ppm_t0, cfg.ppm)
    below = cfg.tier_threshold - volume_before
    above = notional - below
    fee0 = _round_half_up(below * cfg.taker_ppm_t0, cfg.ppm)
    fee1 = _round_half_up(above * cfg.taker_ppm_t1, cfg.ppm)
    return fee0 + fee1


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    return _round_half_up(notional * cfg.maker_rebate_ppm, cfg.ppm)
