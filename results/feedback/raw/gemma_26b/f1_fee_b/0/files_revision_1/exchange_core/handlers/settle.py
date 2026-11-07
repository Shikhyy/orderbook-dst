"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from exchange_core.types import Fill, Report
from exchange_core.intmath import round_half_even
from exchange_core.ledger import (
    transfer_cash,
    adjust_position,
    pay_fee,
    pay_rebate,
    add_volume,
)


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle cash, locks, position, volume, and fees for a fill."""
    cfg = engine.cfg
    state = engine.state
    notional = fill.notional

    # 1. Buyer pays notional from free_cash. Buyer position increases by qty.
    # 2. Seller receives notional in free_cash. Seller position decreases by qty.
    transfer_cash(state, fill.buyer, fill.seller, notional)
    adjust_position(state, fill.buyer, fill.qty)
    adjust_position(state, fill.seller, -fill.qty)

    # 3. Compute taker fee from taker volume before the fill (R-F2).
    # The Fill object has taker_order_id. Determine which account is the taker.
    if fill.taker_order_id == fill.buy_order_id:
        taker_account_id = fill.buyer
    elif fill.taker_order_id == fill.sell_order_id:
        taker_account_id = fill.seller
    else:
        # This case should not be hit based on rules, but as a safety:
        # try to look up the order in state.orders to find the account.
        order = state.orders.get(fill.taker_order_id)
        if order:
            taker_account_id = order.account
        else:
            # Fallback to buyer as in previous attempt, though this is a logic gap.
            taker_account_id = fill.buyer

    taker_volume_before = state.accounts[taker_account_id].volume

    # R-F2: Taker fee calculation
    if taker_volume_before >= cfg.TIER_THRESHOLD:
        fee = round_half_even(notional * cfg.TAKER_PPM_T1, cfg.PPM)
    elif taker_volume_before + notional <= cfg.TIER_THRESHOLD:
        fee = round_half_even(notional * cfg.TAKER_PPM_T0, cfg.PPM)
    else:
        # Split the fill at the threshold
        below = cfg.TIER_THRESHOLD - taker_volume_before
        above = notional - below
        fee = (round_half_even(below * cfg.TAKER_PPM_T0, cfg.PPM) +
               round_half_even(above * cfg.TAKER_PPM_T1, cfg.PPM))

    # 4. Compute maker rebate (R-F3).
    # Maker is the counterpart of the taker.
    if taker_account_id == fill.buyer:
        maker_account_id = fill.seller
    else:
        maker_account_id = fill.buyer

    rebate = round_half_even(notional * cfg.MAKER_REBATE_PPM, cfg.PPM)

    # 5. Taker pays fee from free_cash. Maker receives rebate in free_cash. 
    # fee_vault increases by fee - rebate.
    pay_fee(state, taker_account_id, fee)
    pay_rebate(state, maker_account_id, rebate)

    # 6. Buyer and seller each add notional to their volume (R-F1).
    add_volume(state, fill.buyer, notional)
    add_volume(state, fill.seller, notional)

    # 7. Return a FILL report.
    return [Report.fill(
        buy_order_id=fill.buy_order_id,
        sell_order_id=fill.sell_order_id,
        price=fill.price,
        qty=fill.qty,
        taker_order_id=fill.taker_order_id
    )]
