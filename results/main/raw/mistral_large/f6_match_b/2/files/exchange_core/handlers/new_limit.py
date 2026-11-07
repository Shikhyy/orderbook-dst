"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from typing import Any

from exchange_core.book import (
    add_order,
    best_ask,
    best_bid,
    get_asks,
    get_bids,
    remove_order,
)
from exchange_core.handlers.settle import settle_fill
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Fill, Order, Report


def handle_new_limit(engine: Any, event: Event) -> list[Report]:
    """Process a NEW_LIMIT event and return the reports in order."""
    state = engine.state
    reports: list[Report] = []

    account = state.accounts.get(event.account)
    if account is None:
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    tick = engine.cfg.tick
    if event.qty <= 0 or event.price <= 0 or event.price % tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            ask = best_ask(state)
            if ask is not None and ask <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:
            bid = best_bid(state)
            if bid is not None and bid >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    lock = ceil_div(event.qty * event.price * state.margin_bps, 10_000)
    if account.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

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

    account.free_cash -= lock
    account.locked_margin += lock
    reports.append(Report.accepted(order_id))

    while order.leaves > 0:
        if event.side == "BUY":
            opposite = get_asks(state)
            if not opposite:
                break
            resting = opposite[0]
            if resting.price > event.price:
                break
        else:
            opposite = get_bids(state)
            if not opposite:
                break
            resting = opposite[0]
            if resting.price < event.price:
                break

        if resting.account == event.account:
            remove_order(state, resting.order_id)
            stp_account = state.accounts[resting.account]
            stp_account.locked_margin -= resting.lock
            stp_account.free_cash += resting.lock
            reports.append(Report.cancelled(resting.order_id, "STP"))
            continue

        fill_qty = min(order.leaves, resting.leaves)
        fill_price = resting.price

        order.cum_qty += fill_qty
        resting.cum_qty += fill_qty

        for o in (order, resting):
            new_lock = ceil_div(o.leaves * o.price * o.margin_bps, 10_000)
            released = o.lock - new_lock
            if released:
                acc = state.accounts[o.account]
                acc.locked_margin -= released
                acc.free_cash += released
            o.lock = new_lock

        if event.side == "BUY":
            fill = Fill(
                buy_order_id=order.order_id,
                sell_order_id=resting.order_id,
                price=fill_price,
                qty=fill_qty,
                taker_order_id=order.order_id,
                buyer=order.account,
                seller=resting.account,
            )
        else:
            fill = Fill(
                buy_order_id=resting.order_id,
                sell_order_id=order.order_id,
                price=fill_price,
                qty=fill_qty,
                taker_order_id=order.order_id,
                buyer=resting.account,
                seller=order.account,
            )

        reports.extend(settle_fill(engine, fill))

        if resting.leaves == 0:
            remove_order(state, resting.order_id)

    if event.flag == "IOC":
        if order.leaves > 0:
            reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
            account.locked_margin -= order.lock
            account.free_cash += order.lock
    elif order.leaves > 0:
        add_order(state, order)

    return reports
