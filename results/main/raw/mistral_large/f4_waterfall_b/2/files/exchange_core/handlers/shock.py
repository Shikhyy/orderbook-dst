"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from typing import Any

from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Report


def _in_breach(engine: Any, account: Any, mark_price: int) -> bool:
    position = account.position
    if position == 0:
        return False

    avail = account.free_cash + position * mark_price
    required = ceil_div(abs(position) * mark_price * engine.cfg.MAINT_BPS, 10_000)
    return avail < required


def handle_shock(engine: Any, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    state = engine.state
    mark_price = event.mark_price
    state.mark_price = mark_price

    reports: list[Report] = [Report.mark_set(mark_price)]

    for account_id in sorted(state.accounts):
        if account_id == "LIQ":
            continue

        account = state.accounts[account_id]

        if not _in_breach(engine, account, mark_price):
            continue

        # Stage 1: cancel all resting orders in ascending prio_seq order.
        for order in get_account_orders(state, account_id):
            remove_order(state, order.order_id)
            account.free_cash += order.lock
            account.locked_margin -= order.lock
            reports.append(Report.cancelled(order.order_id, "RISK"))

        # Stage 2: liquidate only if still in breach after Stage 1.
        if not _in_breach(engine, account, mark_price):
            continue

        orig_position = account.position
        notional = abs(orig_position) * mark_price
        liq = state.accounts["LIQ"]

        if orig_position > 0:
            # Account sells to LIQ: LIQ pays, account receives.
            liq.free_cash -= notional
            account.free_cash += notional
        else:
            # Account buys from LIQ: account pays, LIQ receives.
            account.free_cash -= notional
            liq.free_cash += notional

        account.position = 0
        liq.position += orig_position
        reports.append(Report.liquidated(account_id, orig_position))

    return reports
