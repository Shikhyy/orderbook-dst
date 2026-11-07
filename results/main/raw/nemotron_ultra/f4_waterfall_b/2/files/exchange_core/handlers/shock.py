"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Report


def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    state = engine.state
    cfg = engine.cfg
    mark_price = event.mark_price
    
    # R-W1: Set mark_price
    state.mark_price = mark_price
    
    reports = [Report.mark_set(mark_price)]
    
    # Process accounts except LIQ in ascending account-id order
    account_ids = sorted([acc for acc in state.accounts.keys() if acc != "LIQ"])
    
    for acc_id in account_ids:
        acc = state.accounts[acc_id]
        
        # R-W2: Account with position == 0 is never in breach
        if acc.position == 0:
            continue
        
        # Check initial breach
        avail = acc.free_cash + acc.position * mark_price
        req = ceil_div(abs(acc.position) * mark_price * cfg.MAINT_BPS, 10000)
        
        if avail >= req:
            continue  # Not in breach
        
        # R-W3: Stage 1 - cancel all resting orders in ascending prio_seq order
        orders = get_account_orders(state, acc_id)
        for order in orders:
            removed_order = remove_order(state, order.order_id)
            if removed_order:
                # Release lock to free_cash
                state.accounts[acc_id].locked_margin -= removed_order.lock
                state.accounts[acc_id].free_cash += removed_order.lock
                reports.append(Report.cancelled(removed_order.order_id, "RISK"))
        
        # R-W4: Recompute breach after stage 1
        acc = state.accounts[acc_id]  # Refresh reference after lock release
        avail = acc.free_cash + acc.position * mark_price
        req = ceil_div(abs(acc.position) * mark_price * cfg.MAINT_BPS, 10000)
        
        if avail >= req:
            continue  # Breach resolved, no liquidation
        
        # R-W5: Stage 2 - liquidate whole position against LIQ
        orig_position = acc.position
        if orig_position == 0:
            continue  # Safety check
        
        notional = orig_position * mark_price
        
        # Account position becomes 0
        state.accounts[acc_id].position = 0
        # LIQ position changes by opposite amount
        state.accounts["LIQ"].position += orig_position
        
        # Cash transfer: account receives notional, LIQ pays notional
        state.accounts[acc_id].free_cash += notional
        state.accounts["LIQ"].free_cash -= notional
        
        # R-W6: Report liquidation
        reports.append(Report.liquidated(acc_id, orig_position))
    
    return reports
