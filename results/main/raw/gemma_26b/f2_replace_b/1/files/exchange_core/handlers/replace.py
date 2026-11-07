"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.types import Event, Report
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock, lock_cash
from exchange_core.book import best_bid, best_ask


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    order = engine.state.orders.get(event.order_id)

    # R-P2.1: If the order is not resting
    if order is None or order.leaves <= 0:
        return [Report.rejected("UNKNOWN_ORDER")]

    # R-P2.2: Invalid price
    new_price = event.new_price
    if new_price <= 0 or new_price % engine.cfg.TICK != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-P2.3: Invalid quantity
    new_qty = event.new_qty
    if new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    # R-P2.4: Would cross
    if order.side == "BUY":
        ask = best_ask(engine.state)
        if ask is not None and new_price >= ask:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    else:  # side == "SELL"
        bid = best_bid(engine.state)
        if bid is not None and new_price <= bid:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    # R-P2.5: Insufficient margin
    # Calculate new lock using R-P4 logic: ceil_div(new_leaves * new_price * margin_bps, 10000)
    new_leaves = new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * new_price * order.margin_bps, 10000)
    
    old_lock = order.lock
    lock_diff = new_lock - old_lock
    
    if lock_diff > 0:
        account = engine.state.accounts[order.account]
        if lock_diff > account.free_cash:
            return [Report.rejected("INSUFFICIENT_MARGIN")]

    # If we reach here, the REPLACE is valid.
    # Apply changes to state.
    
    # Update margin locks (R-P4)
    if lock_diff > 0:
        lock_cash(engine.state, order.account, lock_diff)
    elif lock_diff < 0:
        release_lock(engine.state, order.account, -lock_diff)

    # R-P3: Priority management
    # If price is same and qty is less than old qty, keep priority.
    # But R-P2.3 says new_qty > cum_qty, so new_qty is at least cum_qty + 1.
    # Thus, "new_qty is less than old qty" is impossible if we respect R-P2.3?
    # Wait, R-P2.3: new_qty <= cum_qty is rejected.
    # If order.qty was 10, cum_qty was 4. leaves was 6.
    # If new_qty is 8, new_leaves is 4. 8 > 4 is true.
    # Rule R-P3 says: "If new_price equals the old price and new_qty is less than the old qty,
    # the order keeps its prio_seq and its place in the queue."
    # Note: new_qty is the TOTAL quantity.
    
    price_changed = new_price != order.price
    qty_increased = new_qty > order.qty
    
    if price_changed or qty_increased:
        order.prio_seq = engine.state.next_prio_seq
        engine.state.next_prio_seq += 1

    # R-P4: Update order fields
    order.price = new_price
    order.qty = new_qty
    order.lock = new_lock

    return [Report.replaced(order.order_id)]
