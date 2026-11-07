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

    # R-B4.1: Check account existence
    acc = get_account(state, event.account)
    if acc is None:
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # R-B4.2: Validate qty and price
    if event.qty <= 0 or event.price <= 0 or event.price % cfg.tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-B4.3: POST_ONLY check
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            asks = get_asks(state)
            if asks and asks[0].price <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:  # SELL
            bids = get_bids(state)
            if bids and bids[0].price >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # R-B4.4: Margin check
    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if acc.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5.1: Assign order_id and prio_seq
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    # R-B5.2: Create order
    # Note: R-B5 uses the current state.margin_bps for the incoming order
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

    # R-B5.3: Update margin
    lock_cash(state, event.account, lock)

    # R-B5.4: Report ACCEPTED
    reports = [Report.accepted(order_id)]

    # R-M1 to R-M4: Matching
    while incoming_order.leaves > 0:
        target_orders = get_asks(state) if incoming_order.side == "BUY" else get_bids(state)
        
        if not target_orders:
            break
        
        best_resting = target_orders[0]
        
        # Check crossing condition
        if incoming_order.side == "BUY":
            if best_resting.price > incoming_order.price:
                break
        else:  # SELL
            if best_resting.price < incoming_order.price:
                break
        
        # R-M3: Self-trade prevention
        if best_resting.account == incoming_order.account:
            # Cancel resting order
            remove_order(state, best_resting.order_id)
            # Move full lock of resting order
            release_lock(state, best_resting.account, best_resting.lock)
            reports.append(Report.cancelled(best_resting.order_id, "STP"))
            continue

        # R-M2: Calculate fill
        fill_qty = min(incoming_order.leaves, best_resting.leaves)
        fill_price = best_resting.price
        
        # R-M4: Effect of fill
        # Construct Fill object for settle_fill
        if incoming_order.side == "BUY":
            buy_order = incoming_order
            sell_order = best_resting
        else:
            buy_order = best_resting
            sell_order = incoming_order

        fill_obj = Fill(
            buy_order_id=buy_order.order_id,
            sell_order_id=sell_order.order_id,
            price=fill_price,
            qty=fill_qty,
            taker_order_id=incoming_order.order_id,
            buyer=buy_order.account,
            seller=sell_order.account
        )

        # 1, 2, 5, 6: Settle via settle_fill (returns [Report.fill])
        fill_reports = settle_fill(engine, fill_obj)
        reports.extend(fill_reports)

        # 3: Update cum_qty
        buy_order.cum_qty += fill_qty
        sell_order.cum_qty += fill_qty

        # 4: Update locks
        for o in (buy_order, sell_order):
            old_lock = o.lock
            new_lock = ceil_div(o.leaves * o.price * o.margin_bps, 10000)
            diff = old_lock - new_lock
            if diff != 0:
                # R-M4.4 says: move old_lock - new_lock from locked_margin to free_cash
                # Note: acc.locked_margin and acc.free_cash are updated via the ledger
                # but we must ensure the instruction is followed.
                # If diff is positive, we move it from locked to free.
                # Since we are inside a loop, we need to use the specific account.
                release_lock(state, o.account, diff)
                o.lock = new_lock
            else:
                o.lock = 0

        # Cleanup resting order if fully filled
        if sell_order.leaves == 0:
            remove_order(state, sell_order.order_id)

    # R-B5.6: IOC remainder
    if incoming_order.flag == "IOC" and incoming_order.leaves > 0:
        reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
        release_lock(state, event.account, incoming_order.lock)
    # R-B5.7: Post remainder to book
    elif incoming_order.leaves > 0:
        add_order(state, incoming_order)

    return reports
