"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.book import add_order, get_asks, get_bids, remove_order
from exchange_core.handlers.settle import settle_fill
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Fill, Order, Report


def _reprice_lock(state, order: Order) -> None:
    """R-M4 step 4: recompute the lock of an order after a fill."""
    new_lock = ceil_div(order.leaves * order.price * order.margin_bps, 10000)
    delta = order.lock - new_lock
    acc = state.accounts[order.account]
    acc.locked_margin -= delta
    acc.free_cash += delta
    order.lock = new_lock


def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a NEW_LIMIT event."""
    state = engine.state
    tick = engine.cfg.tick

    # R-B4 validation
    if event.account not in state.accounts:
        return [Report.rejected("UNKNOWN_ACCOUNT")]
    if event.qty <= 0 or event.price <= 0 or event.price % tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    side = event.side
    price = event.price
    qty = event.qty
    flag = event.flag

    if flag == "POST_ONLY":
        if side == "BUY":
            asks = get_asks(state)
            if asks and asks[0].price <= price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:
            bids = get_bids(state)
            if bids and bids[0].price >= price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    acc = state.accounts[event.account]
    lock = ceil_div(qty * price * state.margin_bps, 10000)
    if acc.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    order = Order(
        order_id=order_id,
        account=event.account,
        side=side,
        price=price,
        qty=qty,
        cum_qty=0,
        prio_seq=prio_seq,
        margin_bps=state.margin_bps,
        lock=lock,
        flag=flag,
    )
    acc.free_cash -= lock
    acc.locked_margin += lock

    reports: list[Report] = [Report.accepted(order_id)]

    # Matching (R-M1 to R-M5)
    while order.leaves > 0:
        if side == "BUY":
            opposite = get_asks(state)
        else:
            opposite = get_bids(state)
        if not opposite:
            break
        resting = opposite[0]
        if side == "BUY":
            if resting.price > price:
                break
        else:
            if resting.price < price:
                break

        if resting.account == order.account:
            # R-M3 self-trade prevention
            remove_order(state, resting.order_id)
            racc = state.accounts[resting.account]
            racc.locked_margin -= resting.lock
            racc.free_cash += resting.lock
            resting.lock = 0
            reports.append(Report.cancelled(resting.order_id, "STP"))
            continue

        q = min(order.leaves, resting.leaves)
        p = resting.price
        if side == "BUY":
            buy_o, sell_o = order, resting
        else:
            buy_o, sell_o = resting, order

        fill = Fill(
            buy_order_id=buy_o.order_id,
            sell_order_id=sell_o.order_id,
            price=p,
            qty=q,
            taker_order_id=order.order_id,
            buyer=buy_o.account,
            seller=sell_o.account,
        )

        # R-M4 steps 3 and 4
        order.cum_qty += q
        resting.cum_qty += q
        _reprice_lock(state, order)
        _reprice_lock(state, resting)

        # Steps 1, 2, 5, 6
        reports.extend(settle_fill(engine, fill))

        if resting.leaves == 0:
            remove_order(state, resting.order_id)

    if order.leaves > 0:
        if flag == "IOC":
            reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
            acc.locked_margin -= order.lock
            acc.free_cash += order.lock
            order.lock = 0
        else:
            add_order(state, order)

    return reports
