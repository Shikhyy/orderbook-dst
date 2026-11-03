"""reference/f1_fee_b/settle.py
Reference solution for task f1_fee_b.
Rules R-M4 (steps 1, 2, 5, 6), R-F1, R-F2, R-F3.
"""
"""reference/f1_fee_a/fee_rule.py
Reference solution for task f1_fee_a.
Rules R-F2 and R-F3.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


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

    Rule R-F3 [Declared]:
    The maker rebate for a fill is round_half_even(notional * MAKER_REBATE_PPM, PPM).
    """
    return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)

from exchange_core.types import Fill, Report


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle the financial effects of a fill.

    Rules R-M4 (1, 2, 5, 6) and R-F1, R-F2, R-F3:
    1. Buyer pays notional from free_cash; buyer position increases by qty.
    2. Seller receives notional in free_cash; seller position decreases by qty.
    3. Compute taker fee using taker volume_before (R-F2).
    4. Compute maker rebate (R-F3).
    5. Taker pays fee from free_cash; maker receives rebate in free_cash; fee_vault updates.
    6. Both accounts have notional added to volume (R-F1).
    7. Return FILL report (R-M4 step 6).
    """
    state = engine.state
    cfg = engine.cfg
    notional = fill.notional

    # Rule R-M4 step 1: buyer cash and position
    state.accounts[fill.buyer].free_cash -= notional
    state.accounts[fill.buyer].position += fill.qty

    # Rule R-M4 step 2: seller cash and position
    state.accounts[fill.seller].free_cash += notional
    state.accounts[fill.seller].position -= fill.qty

    # Determine taker and maker accounts
    if fill.taker_order_id == fill.buy_order_id:
        taker_acc = fill.buyer
        maker_acc = fill.seller
    else:
        taker_acc = fill.seller
        maker_acc = fill.buyer

    # Rule R-F2: compute taker fee using taker volume before fill
    volume_before = state.accounts[taker_acc].volume
    fee = compute_taker_fee(volume_before, notional, cfg)

    # Rule R-F3: compute maker rebate
    rebate = compute_maker_rebate(notional, cfg)

    # Rule R-F3: settle fee and rebate with fee_vault
    state.accounts[taker_acc].free_cash -= fee
    state.accounts[maker_acc].free_cash += rebate
    state.fee_vault += (fee - rebate)

    # Rule R-F1: add notional to both accounts' volume after fee computation
    state.accounts[fill.buyer].volume += notional
    state.accounts[fill.seller].volume += notional

    # Rule R-M4 step 6: FILL report
    return [
        Report.fill(
            buy_order_id=fill.buy_order_id,
            sell_order_id=fill.sell_order_id,
            price=fill.price,
            qty=fill.qty,
            taker_order_id=fill.taker_order_id,
        )
    ]
