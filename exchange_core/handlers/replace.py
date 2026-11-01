"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.book import best_ask, best_bid, get_order
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Report


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4.

    Rejection order (Rule R-P2):
    1. Not resting: UNKNOWN_ORDER
    2. new_price <= 0 or new_price % TICK != 0: INVALID_ORDER
    3. new_qty <= cum_qty: INVALID_REPLACE
    4. New price would match opposite book: REPLACE_WOULD_CROSS
    5. Insufficient margin for lock increase: INSUFFICIENT_MARGIN
    """
    state = engine.state
    cfg = engine.cfg

    # Rule R-P2 step 1: check order is resting
    order = get_order(state, event.order_id)
    if order is None or order.leaves <= 0:
        return [Report.rejected("UNKNOWN_ORDER")]

    # Rule R-P2 step 2: validate new price
    if event.new_price <= 0 or event.new_price % cfg.tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # Rule R-P2 step 3: validate new quantity vs cum_qty
    if event.new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    # Rule R-P2 step 4: crossing check against opposite book
    if order.side == "BUY":
        ask = best_ask(state)
        if ask is not None and ask <= event.new_price:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    elif order.side == "SELL":
        bid = best_bid(state)
        if bid is not None and bid >= event.new_price:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    # Rule R-P2 step 5 & R-P4: margin check using stored order.margin_bps
    new_leaves = event.new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10_000)
    acc = state.accounts[order.account]

    if new_lock > order.lock:
        diff = new_lock - order.lock
        if acc.free_cash < diff:
            return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Rule R-P3: priority update
    if event.new_price == order.price and event.new_qty < order.qty:
        # Quantity decrease: keep priority
        pass
    elif event.new_price == order.price and event.new_qty == order.qty:
        # No-op: nothing changes
        pass
    else:
        # Price change or quantity increase: new priority from counter
        order.prio_seq = state.next_prio_seq
        state.next_prio_seq += 1

    # Rule R-P4: apply changes to order and ledger
    lock_diff = new_lock - order.lock
    acc.free_cash -= lock_diff
    acc.locked_margin += lock_diff

    order.qty = event.new_qty
    order.price = event.new_price
    order.lock = new_lock

    return [Report.replaced(order.order_id)]
