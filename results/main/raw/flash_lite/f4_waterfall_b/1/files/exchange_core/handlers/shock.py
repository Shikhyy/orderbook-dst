"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from exchange_core.types import Event, Report
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock, transfer_cash, adjust_position


def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    engine.state.mark_price = event.mark_price
    reports = [Report.mark_set(event.mark_price)]
    
    maint_bps = engine.cfg.MAINT_BPS
    acc_ids = sorted([aid for aid in engine.state.accounts if aid != "LIQ"])
    
    for acc_id in acc_ids:
        acc = engine.state.accounts[acc_id]
        if acc.position == 0:
            continue
            
        def is_in_breach():
            avail = acc.free_cash + (acc.position * engine.state.mark_price)
            req = ceil_div(abs(acc.position) * engine.state.mark_price * maint_bps, 10000)
            return avail < req

        # Stage 1: Cancel orders
        if is_in_breach():
            orders = get_account_orders(engine.state, acc_id)
            for o in orders:
                remove_order(engine.state, o.order_id)
                release_lock(engine.state, acc_id, o.lock)
                reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))
                if not is_in_breach():
                    break
        
        # Stage 2: Liquidate
        if is_in_breach():
            orig_pos = acc.position
            liq_acc = engine.state.accounts["LIQ"]
            notional = abs(orig_pos) * engine.state.mark_price
            
            if orig_pos > 0:
                # Account sells to LIQ: A receives cash, LIQ pays cash
                transfer_cash(engine.state, "LIQ", acc_id, notional)
            else:
                # Account buys from LIQ: A pays cash, LIQ receives cash
                transfer_cash(engine.state, acc_id, "LIQ", notional)
                
            adjust_position(engine.state, acc_id, -orig_pos)
            adjust_position(engine.state, "LIQ", orig_pos)
            reports.append(Report.liquidated(account=acc_id, qty=orig_pos))
            
    return reports
