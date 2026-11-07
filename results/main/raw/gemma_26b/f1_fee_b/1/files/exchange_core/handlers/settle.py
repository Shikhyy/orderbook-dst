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

    # 1. Buyer pays notional from free_cash. Buyer position increases by qty.
    # 2. Seller receives notional in free_cash. Seller position decreases by qty.
    transfer_cash(state, fill.buyer, fill.seller, notional)
    adjust_position(state, fill.buyer, fill.qty)
    adjust_position(state, fill.seller, -fill.qty)

    # 3. Compute taker fee from taker volume before the fill (R-F2).
    taker_acc = state.accounts[fill.taker_order_id]  # Error in type definition? Fill has taker_order_id, but we need taker account.
    # Wait, the Fill object provided in the interface has 'buyer' and 'seller' fields.
    # We need to identify which one is the taker.
    # The Fill object in the context has buyer, seller, and taker_order_id.
    # However, the taker_order_id refers to an Order. We need the account associated with that order.
    # Looking at the Fill class definition in types.py:
    # @dataclass(frozen=True)
    # class Fill:
    #     buy_order_id: int
    #     sell_order_id: int
    #     price: int
    #     qty: int
    #     taker_order_id: int
    #     buyer: str = ""
    #     seller: str = ""
    #
    # Wait, the taker's account is not explicitly in the Fill object.
    # But the taker_order_id is. We can find the account from state.orders[taker_order_id].
    taker_order = state.orders[fill.taker_order_id]
    taker_account_id = taker_order.account
    taker_acc = state.accounts[taker_account_id]
    
    volume_before = taker_acc.volume
    
    if volume_before >= cfg.TIER_THRESHOLD:
        fee = round_half_even(notional * cfg.TAKER_PPM_T1, cfg.PPM)
    elif volume_before + notional <= cfg.TIER_THRESHOLD:
        fee = round_half_even(notional * cfg.TAKER_PPM_T0, cfg.PPM)
    else:
        below = cfg.TIER_THRESHOLD - volume_before
        above = notional - below
        fee = round_half_even(below * cfg.TAKER_PPM_T0, cfg.PPM) + \
              round_half_even(above * cfg.TAKER_PPM_T1, cfg.PPM)

    # 4. Compute maker rebate (R-F3).
    rebate = round_half_even(notional * cfg.MAKER_REBATE_PPM, cfg.PPM)

    # 5. Taker pays fee from free_cash. Maker receives rebate in free_cash.
    # fee_vault increases by fee - rebate.
    # maker is the non-taker.
    maker_account_id = fill.buyer if taker_account_id == fill.seller else fill.seller
    
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
        taker_order_id=fill.taker_order_id,
    )]
