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

    # R-P2.1: Order must be resting
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    # R-P2.2: Price must be positive and tick-aligned
    if event.new_price <= 0 or event.new_price % engine.cfg.TICK != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-P2.3: new_qty must be greater than cum_qty
    if event.new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    # R-P2.4: Replace cannot result in a cross
    new_leaves = event.new_qty - order.cum_qty
    if order.side == "BUY":
        best_s = best_ask(engine.state)
        if best_s is not None and event.new_price >= best_s:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    else:
        best_b = best_bid(engine.state)
        if best_b is not None and event.new_price <= best_b:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    # R-P2.5: Calculate margin and check against free_cash
    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10000)
    lock_diff = new_lock - order.lock
    
    if lock_diff > 0:
        if engine.state.accounts[order.account].free_cash < lock_diff:
            return [Report.rejected("INSUFFICIENT_MARGIN")]
        lock_cash(engine, order.account, lock_diff)
    elif lock_diff < 0:
        release_lock(engine, order.account, -lock_diff)

    # R-P3: Update priority
    # Keeps priority if price is unchanged and qty is not increased (leaves not increased)
    price_changed = (event.new_price != order.price)
    qty_increased = (new_leaves > order.leaves)
    
    if price_changed or qty_increased:
        order.prio_seq = engine.state.next_prio_seq
        engine.state.next_prio_seq += 1

    # R-P4: Finalize updates
    order.price = event.new_price
    order.qty = event.new_qty
    order.lock = new_lock

    return [Report.replaced(order.order_id)]
