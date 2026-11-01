"""Mutant m_lock_uses_current_rate.
Computes lock with engine margin_bps instead of order.margin_bps.
"""
from exchange_core.book import best_ask, best_bid, get_order
from exchange_core.intmath import ceil_div
from exchange_core.rules.replace_rule import decide_replace
from exchange_core.types import Event, Report


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    state = engine.state
    cfg = engine.cfg

    order = get_order(state, event.order_id)
    if order is None or order.leaves <= 0:
        return [Report.rejected("UNKNOWN_ORDER")]

    dec = decide_replace(order, event.new_price, event.new_qty, cfg)
    if not dec.ok:
        return [Report.rejected(dec.reason)]

    if order.side == "BUY":
        ask = best_ask(state)
        if ask is not None and ask <= event.new_price:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    elif order.side == "SELL":
        bid = best_bid(state)
        if bid is not None and bid >= event.new_price:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    new_leaves = dec.new_leaves
    # BUG: uses state.margin_bps instead of order.margin_bps
    new_lock = ceil_div(new_leaves * event.new_price * state.margin_bps, 10_000)
    acc = state.accounts[order.account]

    if new_lock > order.lock:
        diff = new_lock - order.lock
        if acc.free_cash < diff:
            return [Report.rejected("INSUFFICIENT_MARGIN")]

    if not dec.keep_priority:
        order.prio_seq = state.next_prio_seq
        state.next_prio_seq += 1

    lock_diff = new_lock - order.lock
    acc.free_cash -= lock_diff
    acc.locked_margin += lock_diff

    order.qty = event.new_qty
    order.price = event.new_price
    order.lock = new_lock

    return [Report.replaced(order.order_id)]
