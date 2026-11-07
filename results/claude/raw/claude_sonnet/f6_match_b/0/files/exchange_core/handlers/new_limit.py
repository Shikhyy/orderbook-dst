"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.book import add_order, get_asks, get_bids, remove_order
from exchange_core.handlers.settle import settle_fill
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Fill, Order, Report


def _relock(state, order: Order) -> None:
    """Recompute the lock of an order after a fill and move the difference to free_cash."""
    new_lock = ceil_div(order.leaves * order.price * order.margin_bps, 10000)
    diff = order.lock - new_lock
    acc = state.accounts[order.account]
    acc.locked_margin -= diff
    acc.free_cash += diff
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

    is_buy = event.side == "BUY"

    if event.flag == "POST_ONLY":
        if is_buy:
            asks = get_asks(state)
            if asks and asks[0].price <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:
            bids = get_bids(state)
            if bids and bids[0].price >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    acc = state.accounts[event.account]
    if acc.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5 accept
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
    acc.free_cash -= lock
    acc.locked_margin += lock

    reports: list[Report] = [Report.accepted(order_id)]

    # Matching (R-M1 to R-M5)
    while order.leaves > 0:
        opposite = get_asks(state) if is_buy else get_bids(state)
        if not opposite:
            break
        resting = opposite[0]
        if is_buy:
            crosses = resting.price <= order.price
        else:
            crosses = resting.price >= order.price
        if not crosses:
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
        if is_buy:
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

        # R-M4 step 3
        order.cum_qty += q
        resting.cum_qty += q
        # R-M4 step 4 (R-M5 is the leaves == 0 case)
        _relock(state, order)
        _relock(state, resting)

        # Steps 1, 2, 5, 6
        reports.extend(settle_fill(engine, fill))

        if resting.leaves == 0:
            remove_order(state, resting.order_id)

    if order.leaves > 0:
        if event.flag == "IOC":
            reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
            acc.locked_margin -= order.lock
            acc.free_cash += order.lock
            order.lock = 0
        else:
            add_order(state, order)

    return reports
