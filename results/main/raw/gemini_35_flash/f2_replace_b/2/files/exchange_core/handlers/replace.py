"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.book import best_ask, best_bid, get_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import get_account, lock_cash, release_lock
from exchange_core.types import Event, Report


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    order = get_order(engine.state, event.order_id)
    if order is None or order.leaves <= 0:
        return [Report.rejected("UNKNOWN_ORDER")]

    if event.new_price <= 0 or event.new_price % engine.cfg.TICK != 0:
        return [Report.rejected("INVALID_ORDER")]

    if event.new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    if order.side == "BUY":
        ba = best_ask(engine.state)
        if ba is not None and event.new_price >= ba:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    elif order.side == "SELL":
        bb = best_bid(engine.state)
        if bb is not None and event.new_price <= bb:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    new_leaves = event.new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10000)
    lock_diff = new_lock - order.lock

    acc = get_account(engine.state, order.account)
    if acc is not None and lock_diff > 0 and lock_diff > acc.free_cash:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Rule R-P3: Priority update
    if event.new_price == order.price and event.new_qty <= order.qty:
        pass
    else:
        order.prio_seq = engine.state.next_prio_seq
        engine.state.next_prio_seq += 1

    # Rule R-P4: State updates
    order.qty = event.new_qty
    order.price = event.new_price
    order.lock = new_lock

    if lock_diff > 0:
        lock_cash(engine.state, order.account, lock_diff)
    elif lock_diff < 0:
        release_lock(engine.state, order.account, -lock_diff)

    return [Report.replaced(event.order_id)]
