"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.types import Event, Report
from exchange_core.book import get_order, best_ask, best_bid
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock, lock_cash


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    order = get_order(engine.state, event.order_id)
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    if event.new_price <= 0 or event.new_price % engine.cfg.TICK != 0:
        return [Report.rejected("INVALID_ORDER")]

    if event.new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    # Check for crossing
    if order.side == "BUY":
        best_a = best_ask(engine.state)
        if best_a is not None and event.new_price >= best_a:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    else:
        best_b = best_bid(engine.state)
        if best_b is not None and event.new_price <= best_b:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    # Margin check
    new_leaves = event.new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10000)
    diff = new_lock - order.lock
    if diff > engine.state.accounts[order.account].free_cash:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Apply changes
    # Adjust locks
    if diff > 0:
        lock_cash(engine.state, order.account, diff)
    elif diff < 0:
        release_lock(engine.state, order.account, -diff)

    # Update order
    if not (event.new_price == order.price and event.new_qty == order.qty):
        # Update priority if price changes or qty increases
        order.prio_seq = engine.state.next_prio_seq
        engine.state.next_prio_seq += 1

    order.price = event.new_price
    order.qty = event.new_qty
    order.lock = new_lock

    return [Report.replaced(event.order_id)]
