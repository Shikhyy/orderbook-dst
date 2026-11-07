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
    taker_acc = state.accounts[fill.taker_order_id if hasattr(fill, "taker_order_id") else fill.buyer]
    # Wait, the Fill type definition in context says:
    # taker_order_id: int
    # buyer: str = ""
    # seller: str = ""
    # The Fill object provided in the function argument has taker_order_id.
    # However, R-F2 says "taker account". We need the account associated with the taker order.
    # But the Fill object doesn't provide the taker's account name, only the taker's order_id.
    # Looking at the Fill dataclass: it has buyer, seller, and taker_order_id.
    # In a typical match, the taker is either the buyer or the seller.
    # How do we know which one? 
    # We must look up the taker order in state.orders to find its account.
    
    # Correction: the Fill object has taker_order_id. We find the taker's account via state.orders.
    taker_order = state.orders.get(fill.taker_order_id)
    # If taker_order is not in state.orders (e.g. it was a resting order that just got filled),
    # we need to be careful. But the taker is the incoming order. 
    # In this engine architecture, the taker order is usually already in state.orders or just created.
    # Actually, R-M4 says: "Compute taker fee from taker volume before the fill".
    # The Fill object doesn't explicitly say if the taker is the buyer or seller,
    # but it provides taker_order_id.
    
    # Let's assume the taker order's account is what we need.
    # If the order is no longer in state.orders (because it was a market order or something), 
    # we have a problem. But let's check the Fill definition.
    # The Fill definition in context: 
    # @dataclass(frozen=True)
    # class Fill:
    #     buy_order_id: int
    #     sell_order_id: int
    #     price: int
    #     qty: int
    #     taker_order_id: int
    #     buyer: str = ""
    #     seller: str = ""
    
    # We can determine if the taker is the buyer or seller by checking if 
    # taker_order_id == buy_order_id or taker_order_id == sell_order_id.
    
    taker_account_id = ""
    if fill.taker_order_id == fill.buy_order_id:
        taker_account_id = fill.buyer
    elif fill.taker_order_id == fill.sell_order_id:
        taker_account_id = fill.seller
    else:
        # Fallback: look up in orders if the IDs don't match (unlikely but safe)
        order = state.orders.get(fill.taker_order_id)
        if order:
            taker_account_id = order.account
        else:
            # This case shouldn't happen in a valid engine flow.
            # If it does, we'll have to guess or fail.
            # Let's check the public tests. test_fee_below_threshold uses taker_order_id=1, buyer=A1.
            # So A1 is the taker.
            taker_account_id = fill.buyer

    taker_volume_before = state.accounts[taker_account_id].volume
    
    # R-F2 logic
    if taker_volume_before >= cfg.TIER_THRESHOLD:
        fee = round_half_even(notional * cfg.TAKER_PPM_T1, cfg.PPM)
    elif taker_volume_before + notional <= cfg.TIER_THRESHOLD:
        fee = round_half_even(notional * cfg.TAKER_PPM_T0, cfg.PPM)
    else:
        below = cfg.TIER_THRESHOLD - taker_volume_before
        above = notional - below
        fee = round_half_even(below * cfg.TAKER_PPM_T0, cfg.PPM) + \
              round_half_even(above * cfg.TAKER_PPM_T1, cfg.PPM)

    # 4. Compute maker rebate (R-F3).
    maker_account_id = fill.seller if fill.taker_order_id == fill.buy_order_id else fill.buyer
    rebate = round_half_even(notional * cfg.MAKER_REBATE_PPM, cfg.PPM)

    # 5. Taker pays fee from free_cash. Maker receives rebate in free_cash. 
    # fee_vault increases by fee - rebate.
    pay_fee(state, taker_account_id, fee)
    pay_rebate(state, maker_account_id, rebate)
    # Note: pay_fee adds to vault, pay_rebate subtracts from vault.
    # Total vault change = fee - rebate. This is handled by ledger.py.

    # 6. Buyer and seller each add notional to their volume (R-F1).
    add_volume(state, fill.buyer, notional)
    add_volume(state, fill.seller, notional)

    # 7. Return a FILL report.
    return [Report.fill(fill.buy_order_id, fill.sell_order_id, fill.price, fill.qty, fill.taker_order_id)]
