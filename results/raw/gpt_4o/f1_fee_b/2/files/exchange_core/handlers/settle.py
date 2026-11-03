"""Settlement handler for fills, cash transfer, positions, and fee accounting (Task f1_fee_b).

Rules:
- R-M4: Effect of a fill (steps 1, 2, 5).
- R-F1: Volume tracking.
- R-F2: Taker fee calculation.
- R-F3: Maker rebate calculation.
- R-F4: Fee threshold inclusive boundary.
"""

from typing import Any

from exchange_core.ledger import (
    add_volume,
    adjust_position,
    get_account,
    pay_fee,
    pay_rebate,
    transfer_cash,
)
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


def settle_fill(engine: Any, fill: Fill) -> list[Report]:
    """Settle cash, positions, fees, rebates, and volume for a fill.

    Rules R-M4 (steps 1, 2, 5), R-F1, R-F2, R-F3, R-F4:
    - Step 1: Buyer pays notional from free_cash, buyer position increases by qty.
    - Step 2: Seller receives notional in free_cash, seller position decreases by qty.
    - Step 5: Settle fees:
        - Determine taker and maker from fill.taker_order_id.
        - Taker volume_before is taker volume before this fill.
        - fee = compute_taker_fee(volume_before, notional, engine.cfg)
        - rebate = compute_maker_rebate(notional, engine.cfg)
        - pay_fee: taker pays fee from free_cash to fee_vault
        - pay_rebate: maker receives rebate in free_cash from fee_vault
        - add_volume: add notional to both buyer volume and seller volume
    - Returns FILL report list.
    """
    notional = fill.notional

    # Step 1 & 2: Cash transfer and position adjustment
    transfer_cash(engine.state, fill.buyer, fill.seller, notional)
    adjust_position(engine.state, fill.buyer, fill.qty)
    adjust_position(engine.state, fill.seller, -fill.qty)

    # Step 5: Settle fees and rebates
    if fill.taker_order_id == fill.buy_order_id:
        taker_id = fill.buyer
        maker_id = fill.seller
    else:
        taker_id = fill.seller
        maker_id = fill.buyer

    taker_acc = get_account(engine.state, taker_id)
    volume_before = taker_acc.volume if taker_acc is not None else 0

    fee = compute_taker_fee(volume_before, notional, engine.cfg)
    rebate = compute_maker_rebate(notional, engine.cfg)

    pay_fee(engine.state, taker_id, fee)
    pay_rebate(engine.state, maker_id, rebate)

    add_volume(engine.state, fill.buyer, notional)
    add_volume(engine.state, fill.seller, notional)

    return [
        Report.fill(
            buy_order_id=fill.buy_order_id,
            sell_order_id=fill.sell_order_id,
            price=fill.price,
            qty=fill.qty,
            taker_order_id=fill.taker_order_id,
        )
    ]
