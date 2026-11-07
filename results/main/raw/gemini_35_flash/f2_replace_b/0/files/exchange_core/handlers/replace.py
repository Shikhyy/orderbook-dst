"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from typing import TYPE_CHECKING

from exchange_core.book import best_ask, best_bid, get_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import lock_cash, release_lock
from exchange_core.types import Event, Report

if TYPE_CHECKING:
    from exchange_core.engine import Engine


def handle_replace(engine: "Engine", event: Event) -> list[Report]:
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
    diff = new_lock - order.lock

    if diff > 0:
        acc = engine.state.accounts[order.account]
        if diff > acc.free_cash:
            return [Report.rejected("INSUFFICIENT_MARGIN")]

    if event.new_price == order.price and event.new_qty <= order.qty:
        pass
    else:
        order.prio_seq = engine.state.next_prio_seq
        engine.state.next_prio_seq += 1

    if diff > 0:
        lock_cash(engine.state, order.account, diff)
    elif diff < 0:
        release_lock(engine.state, order.account, -diff)

    order.qty = event.new_qty
    order.price = event.new_price
    order.lock = new_lock

    return [Report.replaced(event.order_id)]
