"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.types import Event, Report
from exchange_core.book import get_order, best_bid, best_ask
from exchange_core.ledger import lock_cash, release_lock
from exchange_core.intmath import ceil_div


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    order = get_order(engine.state, event.order_id)
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    if event.new_price <= 0 or event.new_price % engine.cfg.TICK != 0:
        return [Report.rejected("INVALID_ORDER")]

    if event.new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    if order.side == "BUY":
        best_sell = best_ask(engine.state)
        if best_sell is not None and event.new_price >= best_sell:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    else:
        best_buy = best_bid(engine.state)
        if best_buy is not None and event.new_price <= best_buy:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    new_leaves = event.new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10000)
    diff = new_lock - order.lock

    account = engine.state.accounts[order.account]
    if diff > account.free_cash:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Update state
    if diff > 0:
        lock_cash(engine.state, order.account, diff)
    elif diff < 0:
        release_lock(engine.state, order.account, -diff)

    order.lock = new_lock
    order.qty = event.new_qty
    
    if event.new_price != order.price or event.new_qty > order.qty:
        # Re-eval: Rule R-P3 says "price change, or quantity increase"
        # Since we validated R-P1/R-P2, if price is same and qty increased, trigger new prio
        order.price = event.new_price
        order.prio_seq = engine.state.next_prio_seq
        engine.state.next_prio_seq += 1
    elif event.new_price != order.price:
        order.price = event.new_price
        order.prio_seq = engine.state.next_prio_seq
        engine.state.next_prio_seq += 1
    # else: price same, qty <= old_qty (specifically equal or decrease due to R-P2 check), keep priority

    return [Report.replaced(event.order_id)]
