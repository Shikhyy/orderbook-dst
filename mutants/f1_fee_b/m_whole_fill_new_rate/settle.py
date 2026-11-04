"""mutants/f1_fee_b/m_whole_fill_new_rate/settle.py
Mutant that charges crossing fills wholly at the T1 rate.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even
from exchange_core.types import Fill, Report

# --- Rule logic (fee_rule), written out here because Variant B code may not
# import exchange_core.rules.* (see the task's 'Allowed imports'). ---

def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic.

    Rule R-F2 [Declared]:
    - If volume_before >= TIER_THRESHOLD:
        fee = round_half_even(notional * TAKER_PPM_T1, PPM)
    - If volume_before + notional <= TIER_THRESHOLD:
        fee = round_half_even(notional * TAKER_PPM_T0, PPM)
    - Otherwise the fill crosses the threshold. Split it:
        below = TIER_THRESHOLD - volume_before
        above = notional - below
        fee = round_half_even(below * T0, PPM) + round_half_even(above * T1, PPM)
    The engine rounds each part on its own. It does not round the sum.
    """
    if volume_before >= cfg.tier_threshold:
        # Rule R-F2: above threshold
        return round_half_even(notional * cfg.taker_ppm_t1, cfg.ppm)

    if volume_before + notional <= cfg.tier_threshold:
        # Rule R-F2: below or exactly on threshold
        return round_half_even(notional * cfg.taker_ppm_t0, cfg.ppm)

    # Rule R-F2: crossing fill split
    below = cfg.tier_threshold - volume_before
    above = notional - below
    fee_below = round_half_even(below * cfg.taker_ppm_t0, cfg.ppm)
    fee_above = round_half_even(above * cfg.taker_ppm_t1, cfg.ppm)
    return fee_below + fee_above


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill.

    Rule R-F3 [Declared]:
    The maker rebate for a fill is round_half_even(notional * MAKER_REBATE_PPM, PPM).
    """
    return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    state = engine.state
    cfg = engine.cfg
    notional = fill.notional

    state.accounts[fill.buyer].free_cash -= notional
    state.accounts[fill.buyer].position += fill.qty

    state.accounts[fill.seller].free_cash += notional
    state.accounts[fill.seller].position -= fill.qty

    if fill.taker_order_id == fill.buy_order_id:
        taker_acc = fill.buyer
        maker_acc = fill.seller
    else:
        taker_acc = fill.seller
        maker_acc = fill.buyer

    volume_before = state.accounts[taker_acc].volume
    # Mutant bug: if crossing or above, use T1 for everything
    if volume_before + notional > cfg.tier_threshold:
        fee = round_half_even(notional * cfg.taker_ppm_t1, cfg.ppm)
    else:
        fee = round_half_even(notional * cfg.taker_ppm_t0, cfg.ppm)
    rebate = compute_maker_rebate(notional, cfg)

    state.accounts[taker_acc].free_cash -= fee
    state.accounts[maker_acc].free_cash += rebate
    state.fee_vault += (fee - rebate)

    state.accounts[fill.buyer].volume += notional
    state.accounts[fill.seller].volume += notional

    return [
        Report.fill(
            buy_order_id=fill.buy_order_id,
            sell_order_id=fill.sell_order_id,
            price=fill.price,
            qty=fill.qty,
            taker_order_id=fill.taker_order_id,
        )
    ]
