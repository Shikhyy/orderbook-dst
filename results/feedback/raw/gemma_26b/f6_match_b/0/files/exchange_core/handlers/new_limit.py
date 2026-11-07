"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from typing import Any
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Report, Order, Fill
from exchange_core.intmath import ceil_div
from exchange_core.book import get_asks, get_bids, add_order, remove_order
from exchange_core.ledger import lock_cash, release_lock, get_account


def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a NEW_LIMIT event."""
    state = engine.state
    cfg = engine.cfg

    # R-B4.1: Account existence
    acc_obj = get_account(state, event.account)
    if acc_obj is None:
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # R-B4.2: Invalid order
    if event.qty <= 0 or event.price <= 0 or event.price % cfg.tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-B4.3: POST_ONLY crossing check
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            asks = get_asks(state)
            if asks and asks[0].price <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:
            bids = get_bids(state)
            if bids and bids[0].price >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # R-B4.4: Margin check
    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if acc_obj.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5.1: Assign IDs
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    # R-B5.2 & R-B5.3: Create order and lock margin
    incoming_order = Order(
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
    lock_cash(state, event.account, lock)

    reports: list[Report] = [Report.accepted(order_id)]

    # R-M1: Matching
    while incoming_order.leaves > 0:
        best_opp = None
        if incoming_order.side == "BUY":
            opp_orders = get_asks(state)
            if opp_orders and opp_orders[0].price <= incoming_order.price:
                best_opp = opp_orders[0]
        else:
            opp_orders = get_bids(state)
            if opp_orders and opp_orders[0].price >= incoming_order.price:
                best_opp = opp_orders[0]
        
        if not best_opp:
            break

        # R-M3: Self-trade prevention
        if best_opp.account == incoming_order.account:
            remove_order(state, best_opp.order_id)
            release_lock(state, best_opp.account, best_opp.lock)
            reports.append(Report.cancelled(best_opp.order_id, "STP"))
            continue

        # R-M2: Calculate fill
        fill_qty = min(incoming_order.leaves, best_opp.leaves)
        fill_price = best_opp.price

        if incoming_order.side == "BUY":
            buyer_acc = incoming_order.account
            seller_acc = best_opp.account
            buy_id = incoming_order.order_id
            sell_id = best_opp.order_id
        else:
            buyer_acc = best_opp.account
            seller_acc = incoming_order.account
            buy_id = best_opp.order_id
            sell_id = incoming_order.order_id

        fill = Fill(
            buy_order_id=buy_id,
            sell_order_id=sell_id,
            price=fill_price,
            qty=fill_qty,
            taker_order_id=incoming_order.order_id,
            buyer=buyer_acc,
            seller=seller_acc
        )

        # R-M4: Update cum_qty and locks
        incoming_order.cum_qty += fill_qty
        best_opp.cum_qty += fill_qty

        # Update locks (R-M4.4 / R-M5)
        # Incoming order lock update
        old_inc_lock = incoming_order.lock
        new_inc_lock = ceil_div(incoming_order.leaves * incoming_order.price * incoming_order.margin_bps, 10000)
        diff_inc = old_inc_lock - new_inc_lock
        if diff_inc > 0:
            release_lock(state, incoming_order.account, diff_inc)
        incoming_order.lock = new_inc_lock

        # Best opp lock update
        old_opp_lock = best_opp.lock
        new_opp_lock = ceil_div(best_opp.leaves * best_opp.price * best_opp.margin_bps, 10000)
        diff_opp = old_opp_lock - new_opp_lock
        if diff_opp > 0:
            release_lock(state, best_opp.account, diff_opp)
        best_opp.lock = new_opp_lock

        # R-M4.5/6: Settle and report
        fill_reports = settle_fill(engine, fill)
        reports.extend(fill_reports)

        if best_opp.leaves == 0:
            remove_order(state, best_opp.order_id)

    # R-B5.6 & R-B5.7: Post-match handling
    if incoming_order.leaves > 0:
        if incoming_order.flag == "IOC":
            release_lock(state, incoming_order.account, incoming_order.lock)
            reports.append(Report.cancelled(incoming_order.order_id, "IOC_REMAINDER"))
        else:
            add_order(state, incoming_order)

    return reports
