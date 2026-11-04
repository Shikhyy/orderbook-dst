"""NEW_LIMIT handler: validate, reserve margin, match, settle, rest or cancel."""
from typing import Any

from exchange_core.book import add_order, get_asks, get_bids, remove_order
from exchange_core.handlers.settle import settle_fill
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Fill, Order, Report


def _relock(state: Any, order: Order) -> None:
    """Recompute an order's lock from its leaves and release the difference."""
    new_lock = ceil_div(order.leaves * order.price * order.margin_bps, 10000)
    delta = order.lock - new_lock
    acc = state.accounts[order.account]
    acc.locked_margin -= delta
    acc.free_cash += delta
    order.lock = new_lock


def handle_new_limit(engine: Any, event: Event) -> list[Report]:
    state = engine.state
    tick = engine.cfg.tick
    is_buy = event.side == "BUY"

    # --- validation (R-B4) ---
    acct = state.accounts.get(event.account)
    if acct is None:
        return [Report.rejected("UNKNOWN_ACCOUNT")]
    if event.qty <= 0 or event.price <= 0 or event.price % tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    opposite = get_asks(state) if is_buy else get_bids(state)
    if event.flag == "POST_ONLY" and opposite:
        best = opposite[0].price
        if (is_buy and best <= event.price) or (not is_buy and best >= event.price):
            return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if acct.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # --- accept (R-B5) ---
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1
    order = Order(
        order_id=order_id,
        account=event.account,
        side=event.side,
        price=event.price,
        qty=event.qty,
        cum_qty=0,
        prio_seq=prio_seq,
        margin_bps=state.margin_bps,
        lock=lock,
        flag=event.flag,
    )
    acct.free_cash -= lock
    acct.locked_margin += lock
    reports: list[Report] = [Report.accepted(order_id)]

    # --- matching (R-M1..R-M5) ---
    while order.leaves > 0:
        book = get_asks(state) if is_buy else get_bids(state)
        if not book:
            break
        rest = book[0]
        if is_buy:
            crosses = rest.price <= order.price
        else:
            crosses = rest.price >= order.price
        if not crosses:
            break

        if rest.account == order.account:
            remove_order(state, rest.order_id)
            racc = state.accounts[rest.account]
            racc.locked_margin -= rest.lock
            racc.free_cash += rest.lock
            rest.lock = 0
            reports.append(Report.cancelled(rest.order_id, "STP"))
            continue

        q = min(order.leaves, rest.leaves)
        p = rest.price
        buy_o, sell_o = (order, rest) if is_buy else (rest, order)
        fill = Fill(
            buy_order_id=buy_o.order_id,
            sell_order_id=sell_o.order_id,
            price=p,
            qty=q,
            taker_order_id=order.order_id,
            buyer=buy_o.account,
            seller=sell_o.account,
        )
        order.cum_qty += q
        rest.cum_qty += q
        _relock(state, order)
        _relock(state, rest)
        reports.extend(settle_fill(engine, fill))
        if rest.leaves == 0:
            remove_order(state, rest.order_id)

    # --- remainder ---
    if order.leaves > 0:
        if event.flag == "IOC":
            reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
            acct.locked_margin -= order.lock
            acct.free_cash += order.lock
            order.lock = 0
        else:
            add_order(state, order)
    return reports
