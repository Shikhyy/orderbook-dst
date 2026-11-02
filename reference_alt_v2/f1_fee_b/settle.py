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
from exchange_core.rules.fee_rule import compute_maker_rebate, compute_taker_fee
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
    - Returns empty report list.
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

    return []
