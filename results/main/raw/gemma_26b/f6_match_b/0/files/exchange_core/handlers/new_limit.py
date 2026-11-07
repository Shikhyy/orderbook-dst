"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Fill, Order, Report
from exchange_core.intmath import ceil_div
from exchange_core.book import add_order, remove_order, get_asks, get_bids


def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a NEW_LIMIT event."""
    state = engine.state
    tick = engine.cfg.tick

    # R-B4.1
    if event.account not in state.accounts:
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # R-B4.2
    if event.qty <= 0 or event.price <= 0 or event.price % tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-B4.3
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            asks = get_asks(state)
            if asks and asks[0].price <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:
            bids = get_bids(state)
            if bids and bids[0].price >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # R-B4.4
    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    acc = state.accounts[event.account]
    if acc.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5.1
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    # R-B5.2
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

    # R-B5.3
    acc.free_cash -= lock
    acc.locked_margin += lock

    # R-B5.4
    reports = [Report.accepted(order_id)]

    # R-M1 Matching loop
    while order.leaves > 0:
        if order.side == "BUY":
            candidates = get_asks(state)
            if not candidates or candidates[0].price > order.price:
                break
            best_opp = candidates[0]
        else:
            candidates = get_bids(state)
            if not candidates or candidates[0].price < order.price:
                break
            best_opp = candidates[0]

        # R-M3 STP
        if best_opp.account == order.account:
            remove_order(state, best_opp.order_id)
            opp_acc = state.accounts[best_opp.account]
            opp_acc.free_cash += best_opp.lock
            opp_acc.locked_margin -= best_opp.lock
            reports.append(Report.cancelled(best_opp.order_id, "STP"))
            continue

        # R-M2 Fill
        fill_qty = min(order.leaves, best_opp.leaves)
        fill_price = best_opp.price

        if order.side == "BUY":
            buy_order, sell_order = order, best_opp
        else:
            buy_order, sell_order = best_opp, order

        fill = Fill(
            buy_order_id=buy_order.order_id,
            sell_order_id=sell_order.order_id,
            price=fill_price,
            qty=fill_qty,
            taker_order_id=order.order_id,
            buyer=buy_order.account,
            seller=sell_order.account,
        )

        # R-M4 updates
        # 3. cum_qty
        order.cum_qty += fill_qty
        best_opp.cum_qty += fill_qty

        # 4. new_lock
        # Taker
        old_lock_taker = order.lock
        new_lock_taker = ceil_div(order.leaves * order.price * order.margin_bps, 10000)
        order.lock = new_lock_taker
        acc_taker = state.accounts[order.account]
        acc_taker.locked_margin -= (old_lock_taker - new_lock_taker)
        acc_taker.free_cash += (old_lock_taker - new_lock_taker)

        # Maker
        old_lock_maker = best_opp.lock
        new_lock_maker = ceil_div(best_opp.leaves * best_opp.price * best_opp.margin_bps, 10000)
        best_opp.lock = new_lock_maker
        acc_maker = state.accounts[best_opp.account]
        acc_maker.locked_margin -= (old_lock_maker - new_lock_maker)
        acc_maker.free_cash += (old_lock_maker - new_lock_maker)

        # 5 & 6. Settle and report
        reports.extend(settle_fill(engine, fill))

        # Maker removal if filled
        if best_opp.leaves == 0:
            remove_order(state, best_opp.order_id)

    # R-B5.6 & 5.7
    if order.flag == "IOC" and order.leaves > 0:
        reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
        acc.free_cash += order.lock
        acc.locked_margin -= order.lock
    elif order.leaves > 0:
        add_order(state, order)

    return reports
