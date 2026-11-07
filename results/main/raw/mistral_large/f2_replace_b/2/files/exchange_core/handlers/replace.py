"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4 and R-U3.
"""
from exchange_core.book import best_ask, best_bid, get_order
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Report


def handle_replace(engine: "Engine", event: Event) -> list[Report]:
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    state = engine.state
    order = get_order(state, event.order_id)

    # R-P2.1: only a resting order can be replaced.
    if order is None or order.leaves <= 0:
        return [Report.rejected("UNKNOWN_ORDER")]

    # R-P2.2: price must be positive and on the tick grid.
    tick = engine.cfg.TICK
    if event.new_price <= 0 or event.new_price % tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-P2.3: total quantity must remain above the filled quantity.
    if event.new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    # R-P2.4: the new price must not match the opposite side of the book.
    if order.side == "BUY":
        ask = best_ask(state)
        if ask is not None and event.new_price >= ask:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    else:
        bid = best_bid(state)
        if bid is not None and event.new_price <= bid:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    # R-P4 / R-U3: new lock is based on new leaves and the order's own rate.
    new_leaves = event.new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10_000)
    old_lock = order.lock
    account = state.accounts[order.account]

    # R-P2.5: only an increased lock can fail the margin check.
    if new_lock > old_lock and new_lock - old_lock > account.free_cash:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-P3: priority is kept only for a same-price size reduction or no-op.
    if not (event.new_price == order.price and event.new_qty <= order.qty):
        order.prio_seq = state.next_prio_seq
        state.next_prio_seq += 1

    # R-P4: update the order record.
    order.price = event.new_price
    order.qty = event.new_qty
    order.lock = new_lock

    # R-P4: move the lock difference between free cash and locked margin.
    if new_lock > old_lock:
        diff = new_lock - old_lock
        account.free_cash -= diff
        account.locked_margin += diff
    elif new_lock < old_lock:
        diff = old_lock - new_lock
        account.locked_margin -= diff
        account.free_cash += diff

    return [Report.replaced(order.order_id)]
