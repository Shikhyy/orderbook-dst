"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.types import Event, Report
from exchange_core.intmath import ceil_div
from exchange_core.book import best_bid, best_ask
from exchange_core.ledger import get_account, lock_cash, release_lock


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    order_id = event.order_id
    new_price = event.new_price
    new_qty = event.new_qty

    # R-P2.1: Check if order is resting
    order = engine.state.orders.get(order_id)
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    # R-P2.2: Check price validity
    tick = engine.cfg.TICK
    if new_price <= 0 or new_price % tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-P2.3: Check new_qty > cum_qty
    if new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    # R-P2.4: Check if new price would cross the book
    if order.side == "BUY":
        current_best_ask = best_ask(engine.state)
        if current_best_ask is not None and new_price >= current_best_ask:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    else:  # SELL
        current_best_bid = best_bid(engine.state)
        if current_best_bid is not None and new_price <= current_best_bid:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    # Calculate new lock using order's stored margin_bps
    new_leaves = new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * new_price * order.margin_bps, 10000)

    # R-P2.5: Check margin sufficiency
    if new_lock > order.lock:
        additional_lock = new_lock - order.lock
        account = get_account(engine.state, order.account)
        if account is None or additional_lock > account.free_cash:
            return [Report.rejected("INSUFFICIENT_MARGIN")]

    # All checks passed - perform the replacement
    old_lock = order.lock
    old_price = order.price
    old_qty = order.qty

    # Update order fields
    order.qty = new_qty
    order.price = new_price
    order.lock = new_lock

    # Adjust account margin
    if new_lock > old_lock:
        lock_cash(engine.state, order.account, new_lock - old_lock)
    elif new_lock < old_lock:
        release_lock(engine.state, order.account, old_lock - new_lock)

    # R-P3: Handle priority
    keep_priority = False
    if new_price == old_price:
        if new_qty <= old_qty:
            keep_priority = True
        else:  # new_qty > old_qty
            keep_priority = False
    else:  # price change
        keep_priority = False

    if not keep_priority:
        order.prio_seq = engine.state.next_prio_seq
        engine.state.next_prio_seq += 1

    return [Report.replaced(order_id)]
