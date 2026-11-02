"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1, R-P2, R-P3, R-P4, R-U3.
"""
from typing import Any

from exchange_core.book import best_ask, best_bid, get_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import get_account, lock_cash, release_lock
from exchange_core.rules.replace_rule import decide_replace
from exchange_core.types import Event, Report


def handle_replace(engine: Any, event: Event) -> list[Report]:
    """Handle replace (cancel/replace) event.

    Rules R-P1 to R-P4.
    """
    order = get_order(engine.state, event.order_id)
    # 1. Order not resting
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    # 2 & 3. Validate price and qty using pure rule
    decision = decide_replace(order, event.new_price, event.new_qty, engine.cfg)
    if not decision.ok:
        return [Report.rejected(decision.reason)]

    # 4. Crossing check against opposite book
    if order.side == "BUY":
        ask = best_ask(engine.state)
        if ask is not None and event.new_price >= ask:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    elif order.side == "SELL":
        bid = best_bid(engine.state)
        if bid is not None and event.new_price <= bid:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    # 5. Margin check
    new_leaves = event.new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10_000)
    diff = new_lock - order.lock
    if diff > 0:
        acc = get_account(engine.state, order.account)
        if acc is None or acc.free_cash < diff:
            return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Valid replace: apply state changes
    if not decision.keep_priority:
        order.prio_seq = engine.state.next_prio_seq
        engine.state.next_prio_seq += 1

    order.qty = event.new_qty
    order.price = event.new_price

    if diff > 0:
        lock_cash(engine.state, order.account, diff)
    elif diff < 0:
        release_lock(engine.state, order.account, -diff)
    order.lock = new_lock

    return [Report.replaced(order.order_id)]
