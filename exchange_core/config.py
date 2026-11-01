"""exchange_core/config.py
Configuration constants for the exchange engine.
See docs/04_RULEBOOK.md section 1.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class EngineConfig:
    """Holds engine constants.

    All amounts, prices, and quantities are integers (rule R-U1).
    """
    tick: int = 10_000
    margin_bps_default: int = 2_000
    maint_bps: int = 500
    ppm: int = 1_000_000
    taker_ppm_t0: int = 2_750
    taker_ppm_t1: int = 1_850
    maker_rebate_ppm: int = 250
    tier_threshold: int = 5_000_010_000

    # Aliases matching uppercase notation in docs/04_RULEBOOK.md
    @property
    def TICK(self) -> int: return self.tick
    @property
    def MARGIN_BPS_DEFAULT(self) -> int: return self.margin_bps_default
    @property
    def MAINT_BPS(self) -> int: return self.maint_bps
    @property
    def PPM(self) -> int: return self.ppm
    @property
    def TAKER_PPM_T0(self) -> int: return self.taker_ppm_t0
    @property
    def TAKER_PPM_T1(self) -> int: return self.taker_ppm_t1
    @property
    def MAKER_REBATE_PPM(self) -> int: return self.maker_rebate_ppm
    @property
    def TIER_THRESHOLD(self) -> int: return self.tier_threshold
