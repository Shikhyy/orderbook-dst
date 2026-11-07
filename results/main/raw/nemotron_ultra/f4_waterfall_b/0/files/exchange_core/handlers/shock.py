"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock, transfer_cash, adjust_position
from exchange_core.types import Event, Report


def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    reports: list[Report] = []
    
    # R-W1: Set mark_price and emit MARK_SET
    engine.state.mark_price = event.mark_price
    reports.append(Report.mark_set(event.mark_price))
    
    # Get MAINT_BPS from config
    maint_bps = engine.cfg.MAINT_BPS
    mark_price = engine.state.mark_price
    
    # Process accounts in ascending account-id order, excluding LIQ
    for acc_id in sorted(engine.state.accounts.keys()):
        if acc_id == "LIQ":
            continue
            
        account = engine.state.accounts[acc_id]
        position = account.position
        
        # R-W2: Account with position == 0 is never in breach
        if position == 0:
            continue
        
        # Check breach: avail = free_cash + position * mark_price
        # req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)
        avail = account.free_cash + position * mark_price
        req = ceil_div(abs(position) * mark_price * maint_bps, 10000)
        
        if avail >= req:
            continue  # Not in breach
        
        # R-W3: Stage 1 - cancel all resting orders in ascending prio_seq order
        orders = get_account_orders(engine.state, acc_id)
        for order in orders:
            # Release lock to free_cash
            release_lock(engine.state, acc_id, order.lock)
            # Remove order from book
            remove_order(engine.state, order.order_id)
            # Report cancelled
            reports.append(Report.cancelled(order.order_id, "RISK"))
        
        # R-W4: Recompute breach after stage 1
        avail = account.free_cash + position * mark_price
        if avail >= req:
            continue  # Breach resolved, no liquidation
        
        # R-W5: Stage 2 - liquidate whole position against LIQ
        orig_position = position
        notional = orig_position * mark_price  # signed notional
        
        # Account receives notional (if long, positive; if short, negative)
        # LIQ pays/receives opposite
        transfer_cash(engine.state, "LIQ", acc_id, notional)
        
        # Adjust positions
        adjust_position(engine.state, acc_id, -orig_position)  # Account position becomes 0
        adjust_position(engine.state, "LIQ", orig_position)    # LIQ takes opposite position
        
        # Report liquidation with signed qty (original position)
        reports.append(Report.liquidated(acc_id, orig_position))
    
    return reports
