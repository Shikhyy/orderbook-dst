"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from typing import Any
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock, transfer_cash, adjust_position
from exchange_core.types import Event, Report


def handle_shock(engine: Any, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    reports = [Report.mark_set(mark_price=event.mark_price)]
    engine.state.mark_price = event.mark_price
    maint_bps = engine.cfg.MAINT_BPS

    def is_in_breach(account_id: str) -> bool:
        acc = engine.state.accounts[account_id]
        if acc.position == 0:
            return False
        avail = acc.free_cash + acc.position * engine.state.mark_price
        req = ceil_div(abs(acc.position) * engine.state.mark_price * maint_bps, 10000)
        return avail < req

    account_ids = sorted([aid for aid in engine.state.accounts if aid != "LIQ"])

    for acc_id in account_ids:
        if not is_in_breach(acc_id):
            continue

        # Stage 1: Cancel orders
        orders = get_account_orders(engine.state, acc_id)
        for o in orders:
            remove_order(engine.state, o.order_id)
            release_lock(engine.state, acc_id, o.lock)
            reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))

        # Stage 2: Liquidate if still in breach
        if is_in_breach(acc_id):
            acc = engine.state.accounts[acc_id]
            orig_pos = acc.position
            notional = abs(orig_pos) * engine.state.mark_price

            if orig_pos > 0:
                # Sell: Acc receives notional, LIQ pays notional
                transfer_cash(engine.state, "LIQ", acc_id, notional)
            else:
                # Buy: Acc pays notional, LIQ receives notional
                transfer_cash(engine.state, acc_id, "LIQ", notional)

            adjust_position(engine.state, "LIQ", orig_pos)
            adjust_position(engine.state, acc_id, -orig_pos)
            reports.append(Report.liquidated(account=acc_id, qty=orig_pos))

    return reports
