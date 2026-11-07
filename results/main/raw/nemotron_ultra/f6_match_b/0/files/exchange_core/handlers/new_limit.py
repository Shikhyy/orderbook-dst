"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Report, Fill, Order
from exchange_core.intmath import ceil_div
from exchange_core.book import get_asks, get_bids, best_ask, best_bid, add_order, remove_order
from exchange_core.ledger import has_account, get_account, lock_cash, release_lock


def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a NEW_LIMIT event."""
    state = engine.state
    cfg = engine.cfg
    reports: list[Report] = []

    # R-B4 Validation
    # 1. Account exists
    if not has_account(state, event.account):
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    account = get_account(state, event.account)

    # 2. qty > 0, price > 0, price % tick == 0
    if event.qty <= 0 or event.price <= 0 or event.price % cfg.tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # 3. POST_ONLY would cross
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            ba = best_ask(state)
            if ba is not None and ba <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:  # SELL
            bb = best_bid(state)
            if bb is not None and bb >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # 4. Margin check
    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if account.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5 Valid order processing
    # 1. Assign order_id and prio_seq
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    # 2. Create order
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
        flag=event.flag
    )

    # 3. Lock margin
    lock_cash(state, event.account, lock)

    # 4. Report ACCEPTED
    reports.append(Report.accepted(order_id))

    # 5. Match the order
    while order.leaves > 0:
        # Get opposite side orders in priority order
        if order.side == "BUY":
            opposite_orders = get_asks(state)
            # Check if best ask crosses limit price
            if not opposite_orders or opposite_orders[0].price > order.price:
                break
        else:  # SELL
            opposite_orders = get_bids(state)
            # Check if best bid crosses limit price
            if not opposite_orders or opposite_orders[0].price < order.price:
                break

        # Best opposite order
        resting_order = opposite_orders[0]

        # R-M3 Self-trade prevention
        if resting_order.account == order.account:
            # Cancel resting order with STP
            remove_order(state, resting_order.order_id)
            # Release its lock
            release_lock(state, resting_order.account, resting_order.lock)
            resting_order.lock = 0
            reports.append(Report.cancelled(resting_order.order_id, "STP"))
            continue

        # R-M2 Fill price and quantity
        fill_price = resting_order.price
        fill_qty = min(order.leaves, resting_order.leaves)

        # Create Fill for settle_fill
        if order.side == "BUY":
            buy_order_id = order.order_id
            sell_order_id = resting_order.order_id
            buyer = order.account
            seller = resting_order.account
        else:
            buy_order_id = resting_order.order_id
            sell_order_id = order.order_id
            buyer = resting_order.account
            seller = order.account

        fill = Fill(
            buy_order_id=buy_order_id,
            sell_order_id=sell_order_id,
            price=fill_price,
            qty=fill_qty,
            taker_order_id=order.order_id,
            buyer=buyer,
            seller=seller
        )

        # settle_fill handles R-M4 steps 1, 2, 5, 6
        fill_reports = settle_fill(engine, fill)
        reports.extend(fill_reports)

        # R-M4 step 3: Add q to cum_qty for both orders
        order.cum_qty += fill_qty
        resting_order.cum_qty += fill_qty

        # R-M4 step 4: Update locks for both orders
        # For incoming order
        old_lock = order.lock
        new_lock = ceil_div(order.leaves * order.price * order.margin_bps, 10000)
        if old_lock > new_lock:
            release_lock(state, order.account, old_lock - new_lock)
            order.lock = new_lock

        # For resting order
        old_resting_lock = resting_order.lock
        new_resting_lock = ceil_div(resting_order.leaves * resting_order.price * resting_order.margin_bps, 10000)
        if old_resting_lock > new_resting_lock:
            release_lock(state, resting_order.account, old_resting_lock - new_resting_lock)
            resting_order.lock = new_resting_lock

        # Check if resting order is fully filled
        if resting_order.leaves == 0:
            remove_order(state, resting_order.order_id)

    # After matching: handle remainder
    if order.leaves > 0:
        if order.flag == "IOC":
            # Cancel remainder
            reports.append(Report.cancelled(order.order_id, "IOC_REMAINDER"))
            # Release remaining lock
            release_lock(state, order.account, order.lock)
            order.lock = 0
            # Not stored in state.orders
        else:
            # Add to book as resting order
            add_order(state, order)
    # Else: fully filled, lock already 0, not stored

    return reports
