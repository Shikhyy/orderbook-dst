"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1, R-P2, R-P3, R-P4, R-U3.
"""
from typing import Any

from exchange_core.book import best_ask, best_bid, get_order
from exchange_core.config import EngineConfig
from exchange_core.intmath import ceil_div
from exchange_core.ledger import get_account, lock_cash, release_lock
from exchange_core.types import Event, Order, ReplaceDecision, Report

# --- Rule logic (replace_rule), written out here because Variant B code may not
# import exchange_core.rules.* (see the task's 'Allowed imports'). ---

def decide_replace(
    order: Order,
    new_price: int,
    new_qty: int,
    cfg: EngineConfig,
) -> ReplaceDecision:
    """Decide whether a replace request is valid and whether it keeps priority.

    Rules R-P1, R-P2 (steps 2 and 3), R-P3:
    - Step 2: If new_price <= 0 or new_price % TICK != 0: REJECTED(INVALID_ORDER)
    - Step 3: If new_qty <= cum_qty: REJECTED(INVALID_REPLACE)
    - Priority:
      - If new_price == old_price and new_qty < old_qty: keeps prio_seq
      - If new_price == old_price and new_qty == old_qty: nothing changes (keeps prio_seq)
      - In all other cases (price change or qty increase): gets new prio_seq
    """
    # Rule R-P2 step 2: price validation
    if new_price <= 0 or new_price % cfg.tick != 0:
        return ReplaceDecision(ok=False, reason="INVALID_ORDER", keep_priority=False, new_leaves=0)

    # Rule R-P2 step 3: quantity vs cum_qty
    if new_qty <= order.cum_qty:
        return ReplaceDecision(
            ok=False, reason="INVALID_REPLACE", keep_priority=False, new_leaves=0
        )

    new_leaves = new_qty - order.cum_qty

    # Rule R-P3: priority determination
    if new_price == order.price and new_qty <= order.qty:
        keep_priority = True
    else:
        keep_priority = False

    return ReplaceDecision(
        ok=True,
        reason="",
        keep_priority=keep_priority,
        new_leaves=new_leaves,
    )


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
