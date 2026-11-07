"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from typing import Any

from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Report


def _is_in_breach(engine: Any, account_id: str) -> bool:
    """Rule R-W2: breach test for one account at the current mark price."""
    state = engine.state
    acc = state.accounts[account_id]
    if acc.position == 0:
        return False
    mark = state.mark_price
    avail = acc.free_cash + acc.position * mark
    req = ceil_div(abs(acc.position) * mark * engine.cfg.MAINT_BPS, 10000)
    return avail < req


def handle_shock(engine: Any, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run the margin waterfall for breached accounts."""
    state = engine.state

    # Rule R-W1: set the mark price, then run the waterfall for each account
    # except LIQ, in ascending account-id order.
    state.mark_price = event.mark_price
    reports: list[Report] = [Report.mark_set(mark_price=event.mark_price)]

    for account_id in sorted(state.accounts.keys()):
        if account_id == "LIQ":
            continue
        if not _is_in_breach(engine, account_id):
            continue

        acc = state.accounts[account_id]

        # Rule R-W3: stage 1 - cancel all resting orders in ascending prio_seq
        # order; each cancel releases its lock back to free_cash.
        for order in get_account_orders(state, account_id):
            remove_order(state, order.order_id)
            acc.locked_margin -= order.lock
            acc.free_cash += order.lock
            reports.append(Report.cancelled(order_id=order.order_id, reason="RISK"))

        # Rule R-W4: re-test the breach with the new free_cash; if it is no
        # longer in breach, do not liquidate.
        if not _is_in_breach(engine, account_id):
            continue

        # Rule R-W5: stage 2 - liquidate the whole position at mark_price
        # against the LIQ account. No fee, book unchanged.
        orig_position = acc.position
        mark = state.mark_price
        liq = state.accounts["LIQ"]
        if orig_position > 0:
            # Account sells position units to LIQ: LIQ pays, account receives.
            amount = orig_position * mark
            liq.free_cash -= amount
            acc.free_cash += amount
        else:
            # Account buys abs(position) units from LIQ: account pays, LIQ receives.
            amount = (-orig_position) * mark
            acc.free_cash -= amount
            liq.free_cash += amount
        acc.position = 0
        liq.position += orig_position
        reports.append(Report.liquidated(account=account_id, qty=orig_position))

    return reports
