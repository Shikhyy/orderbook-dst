"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from typing import Any
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock, transfer_cash, adjust_position
from exchange_core.types import Event, Report


def is_in_breach(account_id: str, state: Any, mark_price: int, maint_bps: int) -> bool:
    """R-W2: Check if an account is in breach."""
    acc = state.accounts[account_id]
    if acc.position == 0:
        return False
    avail = acc.free_cash + (acc.position * mark_price)
    req = ceil_div(abs(acc.position) * mark_price * maint_bps, 10000)
    return avail < req


def handle_shock(engine: Any, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    reports = [Report.mark_set(mark_price=event.mark_price)]
    engine.state.mark_price = event.mark_price
    maint_bps = engine.cfg.MAINT_BPS

    # Filter out LIQ and sort accounts by ID
    account_ids = sorted([acc for acc in engine.state.accounts if acc != "LIQ"])

    for acc_id in account_ids:
        # Stage 1: Cancel orders if in breach
        if is_in_breach(acc_id, engine.state, engine.state.mark_price, maint_bps):
            orders = get_account_orders(engine.state, acc_id)
            for o in orders:
                release_lock(engine.state, acc_id, o.lock)
                remove_order(engine.state, o.order_id)
                reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))
                
                # Check breach again after each cancel (R-W4)
                if not is_in_breach(acc_id, engine.state, engine.state.mark_price, maint_bps):
                    break

        # Stage 2: Liquidate if still in breach (R-W5)
        if is_in_breach(acc_id, engine.state, engine.state.mark_price, maint_bps):
            pos = engine.state.accounts[acc_id].position
            notional = abs(pos * engine.state.mark_price)
            
            if pos > 0:
                # Sell to LIQ
                transfer_cash(engine.state, "LIQ", acc_id, notional)
            else:
                # Buy from LIQ
                transfer_cash(engine.state, acc_id, "LIQ", notional)
            
            adjust_position(engine.state, "LIQ", -pos)
            adjust_position(engine.state, acc_id, -pos)
            reports.append(Report.liquidated(account=acc_id, qty=pos))

    return reports
