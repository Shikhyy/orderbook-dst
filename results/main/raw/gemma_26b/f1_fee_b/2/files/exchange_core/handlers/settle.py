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

    # 1. Buyer pays notional. Buyer position increases.
    transfer_cash(state, fill.buyer, fill.seller, notional)
    adjust_position(state, fill.buyer, fill.qty)

    # 2. Seller receives notional. Seller position decreases.
    adjust_position(state, fill.seller, -fill.qty)

    # 3. Compute taker fee (R-F2).
    taker_order = state.orders[fill.taker_order_id]
    taker_account_id = taker_order.account
    taker_acc = state.accounts[taker_account_id]

    volume_before = taker_acc.volume
    threshold = cfg.TIER_THRESHOLD
    ppm = cfg.PPM

    if volume_before >= threshold:
        fee = round_half_even(notional * cfg.TAKER_PPM_T1, ppm)
    elif volume_before + notional <= threshold:
        fee = round_half_even(notional * cfg.TAKER_PPM_T0, ppm)
    else:
        below = threshold - volume_before
        above = notional - below
        fee = round_half_even(below * cfg.TAKER_PPM_T0, ppm) + \
              round_half_even(above * cfg.TAKER_PPM_T1, ppm)

    # 4. Compute maker rebate (R-F3).
    rebate = round_half_even(notional * cfg.MAKER_REBATE_PPM, ppm)

    # 5. Taker pays fee. Maker receives rebate.
    maker_account_id = fill.seller if taker_order.side == "BUY" else fill.buyer
    pay_fee(state, taker_account_id, fee)
    pay_rebate(state, maker_account_id, rebate)

    # 6. Buyer and seller each add notional to their volume (R-F1).
    add_volume(state, fill.buyer, notional)
    add_volume(state, fill.seller, notional)

    # 7. Return FILL report.
    return [Report.fill(fill.buy_order_id, fill.sell_order_id, fill.price, fill.qty, fill.taker_order_id)]
