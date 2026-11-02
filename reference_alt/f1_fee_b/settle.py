"""exchange_core/handlers/settle.py
Settle a fill between two orders.
Rules R-M4, R-F1, R-F2, R-F3, R-U2.
"""
from typing import Any

from exchange_core.ledger import (
    add_volume,
    adjust_position,
    pay_fee,
    pay_rebate,
    transfer_cash,
)
from exchange_core.rules.fee_rule import compute_maker_rebate, compute_taker_fee
from exchange_core.types import Fill, Report


def settle_fill(engine: Any, fill: Fill) -> list[Report]:
    """Apply the financial effects of a fill.

    Rule R-M4:
    1. Buyer pays notional from free_cash, position increases by q.
    2. Seller receives notional in free_cash, position decreases by q.
    3. Settle taker fee and maker rebate (R-F1, R-F2, R-F3).
    4. Return FILL report.
    """
    buyer = fill.buyer
    seller = fill.seller

    if not buyer and fill.buy_order_id in engine.state.orders:
        buyer = engine.state.orders[fill.buy_order_id].account
    if not seller and fill.sell_order_id in engine.state.orders:
        seller = engine.state.orders[fill.sell_order_id].account

    notional = fill.notional
    q = fill.qty

    # 1. Buyer pays notional, position increases by q
    # 2. Seller receives notional, position decreases by q
    transfer_cash(engine.state, buyer, seller, notional)
    adjust_position(engine.state, buyer, q)
    adjust_position(engine.state, seller, -q)

    # 3. Settle fees
    if fill.taker_order_id == fill.buy_order_id:
        taker_acc = buyer
        maker_acc = seller
    else:
        taker_acc = seller
        maker_acc = buyer

    taker_vol_before = engine.state.accounts[taker_acc].volume
    taker_fee = compute_taker_fee(taker_vol_before, notional, engine.cfg)
    maker_rebate = compute_maker_rebate(notional, engine.cfg)

    pay_fee(engine.state, taker_acc, taker_fee)
    pay_rebate(engine.state, maker_acc, maker_rebate)

    add_volume(engine.state, buyer, notional)
    add_volume(engine.state, seller, notional)

    # 4. Report FILL
    return [
        Report.fill(
            buy_order_id=fill.buy_order_id,
            sell_order_id=fill.sell_order_id,
            price=fill.price,
            qty=fill.qty,
            taker_order_id=fill.taker_order_id,
        )
    ]
