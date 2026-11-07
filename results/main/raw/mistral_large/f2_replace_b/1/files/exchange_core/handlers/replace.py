"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4, R-U3.
"""
from exchange_core.book import best_ask, best_bid, get_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import lock_cash, release_lock
from exchange_core.types import Event, Report

_BPS_DENOM = 10_000


def handle_replace(engine: "Engine", event: Event) -> list[Report]:
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    state = engine.state

    order = get_order(state, event.order_id)
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    tick = engine.cfg.TICK
    if event.new_price <= 0 or event.new_price % tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    if event.new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    if order.side == "BUY":
        opposite = best_ask(state)
        if opposite is not None and event.new_price >= opposite:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    else:
        opposite = best_bid(state)
        if opposite is not None and event.new_price <= opposite:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    old_price = order.price
    old_qty = order.qty
    old_lock = order.lock

    new_leaves = event.new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, _BPS_DENOM)

    delta = new_lock - old_lock
    account = state.accounts[order.account]
    if delta > 0 and delta > account.free_cash:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    if delta > 0:
        lock_cash(state, order.account, delta)
    elif delta < 0:
        release_lock(state, order.account, -delta)

    order.price = event.new_price
    order.qty = event.new_qty
    order.lock = new_lock

    if not (event.new_price == old_price and event.new_qty <= old_qty):
        order.prio_seq = state.next_prio_seq
        state.next_prio_seq += 1

    return [Report.replaced(order.order_id)]
