"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.types import Event, Report
from exchange_core.intmath import ceil_div
from exchange_core.ledger import lock_cash, release_lock
from exchange_core.book import best_bid, best_ask


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    # Extract event fields
    order_id = event.order_id
    new_price = event.new_price
    new_qty = event.new_qty

    # Retrieve the order
    order = engine.state.orders.get(order_id)
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]
    # Order must be resting (has unfilled quantity)
    if order.leaves <= 0:
        return [Report.rejected("UNKNOWN_ORDER")]

    # Rule R-P2.2: new_price must be positive and tick-compliant
    if new_price <= 0 or new_price % engine.cfg.TICK != 0:
        return [Report.rejected("INVALID_ORDER")]

    # Rule R-P2.3: new_qty must be greater than cum_qty
    if new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    # Rule R-P2.4: new price must not cross the opposite side of the book
    if order.side == "BUY":
        best_ask_price = best_ask(engine.state)
        if best_ask_price is not None and new_price >= best_ask_price:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    else:  # SELL side
        best_bid_price = best_bid(engine.state)
        if best_bid_price is not None and new_price <= best_bid_price:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    # Compute new lock
    new_leaves = new_qty - order.cum_qty  # new leaves quantity
    new_lock = ceil_div(new_leaves * new_price * order.margin_bps, 10000)

    # Rule R-P2.5: insufficient margin check
    diff = new_lock - order.lock
    acc = engine.state.accounts[order.account]
    if diff > 0 and diff > acc.free_cash:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Adjust cash/lock balances
    if diff > 0:
        lock_cash(engine, order.account, diff)
    elif diff < 0:
        release_lock(engine, order.account, -diff)

    # Update order fields
    order.qty = new_qty
    order.price = new_price
    order.lock = new_lock
    order.leaves = new_leaves

    # Priority handling per R-P3
    if new_price == order.price:
        if new_qty > order.qty:
            # Quantity increase: new priority sequence
            order.prio_seq = engine.next_prio_seq
            engine.next_prio_seq += 1
        # If qty decreases or unchanged, prio_seq stays the same
    else:
        # Price change: new priority sequence
        order.prio_seq = engine.next_prio_seq
        engine.next_prio_seq += 1

    # Successful replace
    return [Report.replaced(order.order_id)]
