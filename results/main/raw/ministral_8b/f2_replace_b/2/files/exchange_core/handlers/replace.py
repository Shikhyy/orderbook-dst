"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import EngineState
from exchange_core.intmath import ceil_div
from exchange_core.config import EngineConfig
from exchange_core.book import get_order
from exchange_core.ledger import get_account, lock_cash, release_lock

def handle_replace(engine: "Engine", event: Event) -> list[Report]:
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    # Check if order exists
    order_id = event.order_id
    order = get_order(engine.state, order_id)
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    # Check if order is resting (has leaves)
    if order.leaves == 0:
        return [Report.rejected("UNKNOWN_ORDER")]

    # Check new_price validity
    new_price = event.new_price
    new_qty = event.new_qty
    if new_price <= 0 or new_price % engine.cfg.TICK != 0:
        return [Report.rejected("INVALID_ORDER")]

    # Check if new_qty is valid (must be greater than cum_qty)
    if new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    # Check if new price would cross the opposite side of the book
    opposite_side = "SELL" if order.side == "BUY" else "BUY"
    best_opposite_price = None
    if opposite_side == "BUY":
        best_opposite_price = engine.state.mark_price  # Assuming mark_price is the best bid
    else:
        best_opposite_price = engine.state.mark_price  # Assuming mark_price is the best ask

    if best_opposite_price is not None and new_price > best_opposite_price:
        return [Report.rejected("REPLACE_WOULD_CROSS")]

    # Check if new lock exceeds free cash
    new_leaves = new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * new_price * order.margin_bps, 10000)
    old_lock = order.lock
    account = get_account(engine.state, order.account)
    if account is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    if new_lock > old_lock and (new_lock - old_lock) > account.free_cash:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Update order fields
    keep_priority = False
    if new_price == order.price and new_qty <= order.qty:
        keep_priority = True

    # Update order
    engine.state.orders[order_id] = order.__class__(
        order_id=order.order_id,
        account=order.account,
        side=order.side,
        price=new_price,
        qty=new_qty,
        cum_qty=order.cum_qty,
        prio_seq=order.prio_seq if keep_priority else engine.state.next_prio_seq,
        margin_bps=order.margin_bps,
        lock=new_lock,
        flag=order.flag
    )

    # Adjust cash and lock
    if not keep_priority:
        engine.state.next_prio_seq += 1

    lock_diff = new_lock - old_lock
    if lock_diff > 0:
        lock_cash(engine.state, order.account, lock_diff)
    else:
        release_lock(engine.state, order.account, -lock_diff)

    return [Report.replaced(order_id)]
