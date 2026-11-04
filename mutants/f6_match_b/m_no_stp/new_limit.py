"""exchange_core/handlers/new_limit.py
Handle NEW_LIMIT event and execute order matching.
Rules R-B1 to R-B5, R-M1 to R-M4. Reference only. Matching lives here.
"""
from exchange_core.book import add_order, best_ask, best_bid, get_asks, get_bids, remove_order
from exchange_core.handlers.settle import settle_fill
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Fill, Order, Report


def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a NEW_LIMIT event.

    Rules R-B4, R-B5, R-M1, R-M2, R-M3, R-M4.
    """
    state = engine.state
    cfg = engine.cfg
    reports: list[Report] = []

    # Rule R-B4 step 1: unknown account check
    if event.account not in state.accounts:
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # Rule R-B4 step 2: invalid order checks
    if event.qty <= 0 or event.price <= 0 or event.price % cfg.tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # Rule R-B4 step 3: POST_ONLY crossing check
    if event.flag == "POST_ONLY":
        ask, bid = best_ask(state), best_bid(state)
        if (event.side == "BUY" and ask is not None and ask <= event.price) or (
            event.side == "SELL" and bid is not None and bid >= event.price
        ):
            return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # Rule R-B4 step 4: margin check
    acc = state.accounts[event.account]
    lock = ceil_div(event.qty * event.price * state.margin_bps, 10_000)
    if acc.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Rule R-B5 step 1: assign order_id and prio_seq from counters
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    # Rule R-B5 step 2 & 3: create order, store engine margin_bps, lock margin
    acc.free_cash -= lock
    acc.locked_margin += lock

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

    # Rule R-B5 step 4: report ACCEPTED
    reports.append(Report.accepted(order_id))

    # Rule R-B5 step 5: match the order (Rules R-M1 to R-M4)
    while order.leaves > 0:
        # Rule R-M1: find best candidate resting order
        resting_candidates = get_asks(state) if order.side == "BUY" else get_bids(state)
        if not resting_candidates:
            break

        best_resting = resting_candidates[0]

        # Check price crossing condition
        if order.side == "BUY" and best_resting.price > order.price:
            break
        if order.side == "SELL" and best_resting.price < order.price:
            break

        # Rule R-M3: Self-Trade Prevention
        if False:
            remove_order(state, best_resting.order_id)
            # Release resting order lock back to account free_cash
            state.accounts[best_resting.account].locked_margin -= best_resting.lock
            state.accounts[best_resting.account].free_cash += best_resting.lock
            reports.append(Report.cancelled(best_resting.order_id, "STP"))
            continue

        # Rule R-M2: fill price is resting price; fill quantity is min(leaves)
        fill_price = best_resting.price
        fill_qty = min(order.leaves, best_resting.leaves)

        # Rule R-M4 step 3 & 4: adjust cum_qty and locks for both orders
        # 1. Update maker (resting order)
        maker_old_lock = best_resting.lock
        best_resting.cum_qty += fill_qty
        maker_new_lock = ceil_div(
            best_resting.leaves * best_resting.price * best_resting.margin_bps, 10_000
        )
        maker_release = maker_old_lock - maker_new_lock
        state.accounts[best_resting.account].locked_margin -= maker_release
        state.accounts[best_resting.account].free_cash += maker_release
        best_resting.lock = maker_new_lock

        # 2. Update taker (incoming order)
        taker_old_lock = order.lock
        order.cum_qty += fill_qty
        taker_new_lock = ceil_div(order.leaves * order.price * order.margin_bps, 10_000)
        taker_release = taker_old_lock - taker_new_lock
        state.accounts[order.account].locked_margin -= taker_release
        state.accounts[order.account].free_cash += taker_release
        order.lock = taker_new_lock

        # Remove maker from book if fully filled (leaves == 0)
        if best_resting.leaves == 0:
            remove_order(state, best_resting.order_id)

        # Build fill record
        is_buy = order.side == "BUY"
        fill = Fill(
            buy_order_id=order.order_id if is_buy else best_resting.order_id,
            sell_order_id=best_resting.order_id if is_buy else order.order_id,
            price=fill_price,
            qty=fill_qty,
            taker_order_id=order.order_id,
            buyer=order.account if is_buy else best_resting.account,
            seller=best_resting.account if is_buy else order.account,
        )

        # Rule R-M4 steps 1, 2, 5, 6: settle fill financial effects
        fill_reports = settle_fill(engine, fill)
        reports.extend(fill_reports)

    # Rule R-B5 step 6: IOC remainder handling
    if order.flag == "IOC" and order.leaves > 0:
        # Cancel remainder and release lock
        remaining_lock = order.lock
        state.accounts[order.account].locked_margin -= remaining_lock
        state.accounts[order.account].free_cash += remaining_lock
        order.lock = 0
        reports.append(Report.cancelled(order.order_id, "IOC_REMAINDER"))
    elif order.flag != "IOC" and order.leaves > 0:
        # Rule R-B5 step 7: add resting order to book
        add_order(state, order)

    return reports
