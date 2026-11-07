"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from typing import Any

from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import adjust_position, release_lock, transfer_cash
from exchange_core.types import Event, Report


def handle_shock(engine: Any, event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    # R-W1: Set mark price
    engine.state.mark_price = event.mark_price
    reports: list[Report] = [Report.mark_set(event.mark_price)]

    # R-W1: Accounts in ascending order, except LIQ
    sorted_account_ids = sorted(engine.state.accounts.keys())
    if "LIQ" in sorted_account_ids:
        sorted_account_ids.remove("LIQ")

    for acc_id in sorted_account_ids:
        acc = engine.state.accounts[acc_id]
        pos = acc.position

        if pos == 0:
            continue

        # R-W2: Breach test
        # avail = free_cash + position * mark_price
        # req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)
        def is_in_breach(a: Any) -> bool:
            avail = a.free_cash + a.position * engine.state.mark_price
            req = ceil_div(abs(a.position) * engine.state.mark_price * engine.cfg.MAINT_BPS, 10000)
            return avail < req

        if not is_in_breach(acc):
            continue

        # Stage 1: Cancel resting orders
        # R-W3: Ascending prio_seq order
        orders = get_account_orders(engine.state, acc_id)
        for o in orders:
            # Each cancel releases lock to free_cash
            # Rule R-W3: reports CANCELLED(order_id, RISK)
            # Note: Rule R-W3 says "releases the lock to free_cash". 
            # Based on standard logic, this means acc.free_cash += o.lock; acc.locked_margin -= o.lock
            # We use release_lock from ledger for this.
            amount_to_release = o.lock
            release_lock(engine.state, acc_id, amount_to_release)
            remove_order(engine.state, o.order_id)
            reports.append(Report.cancelled(o.order_id, "RISK"))

        # R-W4: Re-test breach after Stage 1
        if not is_in_breach(acc):
            continue

        # Stage 2: Liquidation
        # R-W5: Liquidate whole position at mark_price against LIQ
        # If pos > 0: account sells pos units to LIQ. Acc receives pos * mark_price. LIQ pays.
        # If pos < 0: account buys abs(pos) units from LIQ. Acc pays abs(pos) * mark_price. LIQ receives.
        orig_pos = pos
        notional = abs(orig_pos) * engine.state.mark_price
        liq_acc = engine.state.accounts["LIQ"]

        if orig_pos > 0:
            # Account sells (long -> 0)
            transfer_cash(engine.state, "LIQ", acc_id, notional)
        else:
            # Account buys (short -> 0)
            transfer_cash(engine.state, acc_id, "LIQ", notional)

        # Update positions
        adjust_position(engine.state, acc_id, -orig_pos)
        adjust_position(engine.state, "LIQ", orig_pos)

        reports.append(Report.liquidated(acc_id, orig_pos))

    return reports
