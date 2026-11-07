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
    taker_acc = state.accounts[fill.taker_order_id if hasattr(fill, "taker_order_id") else fill.buyer]
    # Actually, taker_order_id is provided in Fill. We need the account associated with it.
    # The Fill type has taker_order_id, but the taker account is either buyer or seller.
    # We need to determine which one is the taker.
    # In most matching engines, the taker is the aggressor. 
    # Looking at the Fill type, it contains taker_order_id.
    # We need the account of the taker. 
    # Let's find the taker account by checking which order matches taker_order_id.
    # However, the Fill object in the context doesn't directly say which side is taker.
    # But the task says: "Compute taker fee from taker volume before the fill".
    # The taker account is the one that submitted the taker_order_id.
    # We can find the account by looking up the order in state.orders.
    
    taker_account_id = ""
    taker_order = state.orders.get(fill.taker_order_id)
    if taker_order:
        taker_account_id = taker_order.account
    else:
        # Fallback: if order is not in resting orders (it was an incoming order),
        # we need to know which side it was. 
        # In the context of a fill, the taker is the one who didn't have a resting order.
        # But the Fill object passed to us is complete.
        # Let's assume we can identify the taker account.
        # Wait, the Fill object in the public tests shows:
        # Fill(buy_order_id=1, sell_order_id=2, price=100_000_000, qty=10, taker_order_id=1, buyer="A1", seller="A2")
        # Here taker_order_id=1, which is the buy_order_id. Buyer is A1.
        # So taker is A1.
        pass

    # Re-evaluating how to find taker account:
    # The Fill object contains taker_order_id. The order itself is not in state.orders 
    # if it's an incoming order. However, the Fill object MUST be able to identify the taker.
    # In the provided test: fill.taker_order_id is used.
    # We need to know if the taker was the buyer or the seller.
    # In the test_cash_transfer, taker_order_id=1, buyer="A1", sell_order_id=2.
    # Since taker_order_id is 1, and 1 is the buy_order_id, the taker is the buyer.
    
    # We'll check which side the taker_order_id belongs to.
    # But we don't have the taker side in Fill? 
    # Actually, we can infer it: if the taker_order_id is the buy_order_id, the taker is the buyer.
    # If it's the sell_order_id, the taker is the seller.
    # But what if the taker is not one of those? The rules say "taker_order_id".
    # Let's look at the Fill definition: taker_order_id: int.
    # In the provided test cases, taker_order_id matches either buy_order_id or sell_order_id.
    
    if fill.taker_order_id == fill.buy_order_id:
        taker_acc_id = fill.buyer
    elif fill.taker_order_id == fill.sell_order_id:
        taker_acc_id = fill.seller
    else:
        # This shouldn't happen based on the schema/tests, but for robustness:
        # Try to find it in state.orders.
        taker_order = state.orders.get(fill.taker_order_id)
        if taker_order:
            taker_acc_id = taker_order.account
        else:
            # This is a fallback. In a real engine, the taker account is known.
            # Given the constraints, we assume taker_order_id matches one of the sides.
            taker_acc_id = fill.buyer 

    taker_volume_before = state.accounts[taker_acc_id].volume
    
    # R-F2: Fee Calculation
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
