"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import EngineState
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.config import EngineConfig

def handle_shock(engine: EngineState, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    reports = []
    mark_price = event.mark_price
    reports.append(Report.mark_set(mark_price=mark_price))
    engine.mark_price = mark_price

    # Get MAINT_BPS from config
    maint_bps = engine.cfg.MAINT_BPS

    # Process accounts in ascending order
    accounts_sorted = sorted(engine.state.accounts.keys())
    for acc_id in accounts_sorted:
        if acc_id == "LIQ":
            continue

        acc = engine.state.accounts[acc_id]
        position = acc.position
        free_cash = acc.free_cash
        locked_margin = acc.locked_margin

        if position == 0:
            continue

        # Calculate available and required margin
        avail = free_cash + position * mark_price
        req = ceil_div(abs(position) * mark_price * maint_bps, 10000)

        if avail >= req:
            continue

        # Stage 1: Cancel resting orders
        cancelled_orders = []
        account_orders = get_account_orders(engine.state, acc_id)
        for order in account_orders:
            cancelled_orders.append(order.order_id)
            remove_order(engine.state, order.order_id)
            reports.append(Report.cancelled(order_id=order.order_id, reason="RISK"))

        # Recalculate available margin after cancelling orders
        avail = free_cash + position * mark_price
        req = ceil_div(abs(position) * mark_price * maint_bps, 10000)

        if avail >= req:
            continue

        # Stage 2: Liquidate position
        reports.append(Report.liquidated(account=acc_id, qty=position))

        # Update positions and cash
        liq_acc = engine.state.accounts["LIQ"]
        if position > 0:
            # Sell position to LIQ
            transfer_amount = position * mark_price
            engine.state.accounts[acc_id].free_cash += transfer_amount
            engine.state.accounts["LIQ"].free_cash -= transfer_amount
            engine.state.accounts["LIQ"].position += position
        else:
            # Buy position from LIQ
            transfer_amount = abs(position) * mark_price
            engine.state.accounts[acc_id].free_cash -= transfer_amount
            engine.state.accounts["LIQ"].free_cash += transfer_amount
            engine.state.accounts["LIQ"].position += position

        # Set position to 0
        engine.state.accounts[acc_id].position = 0

    return reports
