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
    state = engine.state
    cfg = engine.cfg
    notional = fill.notional

    # 1. Buyer pays notional (price * qty) from free_cash. Buyer position increases by qty.
    # 2. Seller receives notional in free_cash. Seller position decreases by qty.
    transfer_cash(state, fill.buyer, fill.seller, notional)
    adjust_position(state, fill.buyer, fill.qty)
    adjust_position(state, fill.seller, -fill.qty)

    # 3. Compute taker fee from taker volume before the fill (R-F2).
    # We identify the taker account by checking which side the taker_order_id belongs to.
    if fill.taker_order_id == fill.buy_order_id:
        taker_acc_id = fill.buyer
    elif fill.taker_order_id == fill.sell_order_id:
        taker_acc_id = fill.seller
    else:
        # Fallback if taker_order_id is not one of the two match sides (should not happen in valid fills)
        # In a real system, we would look up the order or rely on a 'taker_side' field.
        taker_acc_id = fill.buyer

    taker_volume_before = state.accounts[taker_acc_id].volume

    # R-F2: Taker fee calculation
    if taker_volume_before >= cfg.TIER_THRESHOLD:
        fee = round_half_even(notional * cfg.TAKER_PPM_T1, cfg.PPM)
    elif taker_volume_before + notional <= cfg.TIER_THRESHOLD:
        fee = round_half_even(notional * cfg.TAKER_PPM_T0, cfg.PPM)
    else:
        # Fill crosses the threshold
        below = cfg.TIER_THRESHOLD - taker_volume_before
        above = notional - below
        fee = (round_half_even(below * cfg.TAKER_PPM_T0, cfg.PPM) +
               round_half_even(above * cfg.TAKER_PPM_T1, cfg.PPM))

    # 4. Compute maker rebate (R-F3).
    # Maker is the counterpart to the taker.
    maker_acc_id = fill.seller if taker_acc_id == fill.buyer else fill.buyer
    rebate = round_half_even(notional * cfg.MAKER_REBATE_PPM, cfg.PPM)

    # 5. Taker pays fee from free_cash. Maker receives rebate in free_cash.
    # fee_vault increases by fee - rebate.
    pay_fee(state, taker_acc_id, fee)
    pay_rebate(state, maker_acc_id, rebate)

    # 6. Buyer and seller each add notional to their volume (R-F1).
    add_volume(state, fill.buyer, notional)
    add_volume(state, fill.seller, notional)

    # 7. Return a FILL report.
    return [Report.fill(
        buy_order_id=fill.buy_order_id,
        sell_order_id=fill.sell_order_id,
        price=fill.price,
        qty=fill.qty,
        taker_order_id=fill.taker_order_id,
    )]
