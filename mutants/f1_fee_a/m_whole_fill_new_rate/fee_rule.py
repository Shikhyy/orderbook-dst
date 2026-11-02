"""mutants/f1_fee_a/m_whole_fill_new_rate/fee_rule.py
Mutant that applies T1 rate to the entire crossing fill.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    if volume_before >= cfg.tier_threshold:
        return round_half_even(notional * cfg.taker_ppm_t1, cfg.ppm)
    if volume_before + notional <= cfg.tier_threshold:
        return round_half_even(notional * cfg.taker_ppm_t0, cfg.ppm)
    # Mutant bug: whole fill at new rate T1
    return round_half_even(notional * cfg.taker_ppm_t1, cfg.ppm)


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)
