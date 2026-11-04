"""Mutant m_lock_uses_current_rate.
Computes lock with engine margin_bps instead of order.margin_bps.
"""
from exchange_core.book import best_ask, best_bid, get_order
from exchange_core.config import EngineConfig
from exchange_core.intmath import ceil_div
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
