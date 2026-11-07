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
    # R-W1: Set mark_price
    engine.state.mark_price = event.mark_price
    reports: list[Report] = [Report.mark_set(mark_price=event.mark_price)]

    # R-W1: Accounts in ascending order, excluding LIQ
    sorted_accounts = sorted(
        [acc_id for acc_id in engine.state.accounts if acc_id != "LIQ"],
        key=lambda x: x
    )

    for acc_id in sorted_accounts:
        acc = engine.state.accounts[acc_id]
        pos = acc.position

        # R-W2: If position == 0, never in breach
        if pos == 0:
            continue

        # R-W2: Breach test
        # avail = free_cash + position * mark_price
        # req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)
        def is_in_breach(current_acc: Any) -> bool:
            avail = current_acc.free_cash + (current_acc.position * engine.state.mark_price)
            req = ceil_div(abs(current_acc.position) * engine.state.mark_price * engine.cfg.MAINT_BPS, 10000)
            return avail < req

        # Stage 1: Cancel orders
        if is_in_breach(acc):
            # R-W3: Cancel all resting orders in ascending prio_seq order
            orders = get_account_orders(engine.state, acc_id)
            for o in orders:
                # Each cancel releases the lock to free_cash
                # Rule R-W3 says "Each cancel releases the lock to free_cash"
                # We must use the amount currently locked by the order.
                lock_amount = o.lock
                remove_order(engine.state, o.order_id)
                release_lock(engine.state, acc_id, lock_amount)
                reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))

            # R-W4: Re-test breach after Stage 1
            if is_in_breach(acc):
                # Stage 2: Liquidation
                # R-W5: Liquidate whole position at mark_price against LIQ
                orig_pos = acc.position
                notional = abs(orig_pos) * engine.state.mark_price

                if orig_pos > 0:
                    # Account sells to LIQ: Account receives notional, LIQ pays notional
                    transfer_cash(engine.state, "LIQ", acc_id, notional)
                    adjust_position(engine.state, "LIQ", orig_pos)
                else:
                    # Account buys from LIQ: Account pays notional, LIQ receives notional
                    transfer_cash(engine.state, acc_id, "LIQ", notional)
                    adjust_position(engine.state, "LIQ", orig_pos)

                acc.position = 0
                acc.locked_margin = 0
                reports.append(Report.liquidated(account=acc_id, qty=orig_pos))

    return reports
