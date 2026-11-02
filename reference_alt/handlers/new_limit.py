"""exchange_core/handlers/new_limit.py
Handle NEW_LIMIT event.
Rules R-B4, R-B5, R-M1, R-M2, R-M3, R-M4.
"""
from typing import Any

from exchange_core.book import add_order, best_ask, best_bid, get_asks, get_bids, remove_order
from exchange_core.handlers.settle import settle_fill
from exchange_core.intmath import ceil_div
from exchange_core.ledger import get_account, has_account, lock_cash, release_lock
from exchange_core.types import Event, Fill, Order, Report


def handle_new_limit(engine: Any, event: Event) -> list[Report]:
    """Validate, accept, match, and book a new limit order."""
    # R-B4 validation
    # 1. Unknown account
    if not has_account(engine.state, event.account):
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # 2. Invalid order parameters
    if event.qty <= 0 or event.price <= 0 or event.price % engine.cfg.tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # 3. Post-only crossing check
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            ask = best_ask(engine.state)
            if ask is not None and event.price >= ask:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        elif event.side == "SELL":
            bid = best_bid(engine.state)
            if bid is not None and event.price <= bid:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # 4. Insufficient margin
    lock = ceil_div(event.qty * event.price * engine.state.margin_bps, 10_000)
    acc = get_account(engine.state, event.account)
    if acc is None or acc.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5: Order is valid
    order_id = engine.state.next_order_id
    engine.state.next_order_id += 1
    prio_seq = engine.state.next_prio_seq
    engine.state.next_prio_seq += 1

    order = Order(
        order_id=order_id,
        account=event.account,
        side=event.side,
        price=event.price,
        qty=event.qty,
        cum_qty=0,
        prio_seq=prio_seq,
        margin_bps=engine.state.margin_bps,
        lock=lock,
        flag=event.flag,
    )

    lock_cash(engine.state, event.account, lock)
    add_order(engine.state, order)

    reports: list[Report] = [Report.accepted(order_id)]

    # Match order
    if order.side == "BUY":
        while order.leaves > 0:
            asks = get_asks(engine.state)
            if not asks:
                break
            resting = asks[0]
            if resting.price > order.price:
                break
            if resting.account == order.account:
                # Self-trade prevention (R-M3)
                remove_order(engine.state, resting.order_id)
                release_lock(engine.state, resting.account, resting.lock)
                resting.lock = 0
                reports.append(Report.cancelled(resting.order_id, "STP"))
                continue

            fill_qty = min(order.leaves, resting.leaves)

            # R-M4: Add q to cum_qty
            order.cum_qty += fill_qty
            resting.cum_qty += fill_qty

            # R-M4: Recompute locks and release difference
            new_order_lock = ceil_div(order.leaves * order.price * order.margin_bps, 10_000)
            diff_order = order.lock - new_order_lock
            if diff_order > 0:
                release_lock(engine.state, order.account, diff_order)
            order.lock = new_order_lock

            new_resting_lock = ceil_div(resting.leaves * resting.price * resting.margin_bps, 10_000)
            diff_resting = resting.lock - new_resting_lock
            if diff_resting > 0:
                release_lock(engine.state, resting.account, diff_resting)
            resting.lock = new_resting_lock

            if resting.leaves == 0:
                remove_order(engine.state, resting.order_id)

            fill = Fill(
                buy_order_id=order.order_id,
                sell_order_id=resting.order_id,
                price=resting.price,
                qty=fill_qty,
                taker_order_id=order.order_id,
                buyer=order.account,
                seller=resting.account,
            )
            reports.extend(settle_fill(engine, fill))
    else:  # SELL
        while order.leaves > 0:
            bids = get_bids(engine.state)
            if not bids:
                break
            resting = bids[0]
            if resting.price < order.price:
                break
            if resting.account == order.account:
                # Self-trade prevention (R-M3)
                remove_order(engine.state, resting.order_id)
                release_lock(engine.state, resting.account, resting.lock)
                resting.lock = 0
                reports.append(Report.cancelled(resting.order_id, "STP"))
                continue

            fill_qty = min(order.leaves, resting.leaves)

            # R-M4: Add q to cum_qty
            order.cum_qty += fill_qty
            resting.cum_qty += fill_qty

            # R-M4: Recompute locks and release difference
            new_order_lock = ceil_div(order.leaves * order.price * order.margin_bps, 10_000)
            diff_order = order.lock - new_order_lock
            if diff_order > 0:
                release_lock(engine.state, order.account, diff_order)
            order.lock = new_order_lock

            new_resting_lock = ceil_div(resting.leaves * resting.price * resting.margin_bps, 10_000)
            diff_resting = resting.lock - new_resting_lock
            if diff_resting > 0:
                release_lock(engine.state, resting.account, diff_resting)
            resting.lock = new_resting_lock

            if resting.leaves == 0:
                remove_order(engine.state, resting.order_id)

            fill = Fill(
                buy_order_id=resting.order_id,
                sell_order_id=order.order_id,
                price=resting.price,
                qty=fill_qty,
                taker_order_id=order.order_id,
                buyer=resting.account,
                seller=order.account,
            )
            reports.extend(settle_fill(engine, fill))

    # Post-match cleanup
    if order.leaves > 0:
        if order.flag == "IOC":
            remove_order(engine.state, order.order_id)
            release_lock(engine.state, order.account, order.lock)
            order.lock = 0
            reports.append(Report.cancelled(order.order_id, "IOC_REMAINDER"))
    else:
        # leaves == 0, remove if not already removed by settle_fill
        remove_order(engine.state, order.order_id)

    return reports
