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
    tick = engine.cfg.tick

    # R-B4.1: Account exists
    acc = get_account(state, event.account)
    if acc is None:
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # R-B4.2: Invalid order
    if event.qty <= 0 or event.price <= 0 or event.price % tick != 0:
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
    lock_val = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if acc.free_cash < lock_val:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5.1: Assign IDs
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    # R-B5.2 & R-B5.3: Create order and reserve margin
    # We store the margin_bps from the state at the time of order creation
    order = Order(
        order_id=order_id,
        account=event.account,
        side=event.side,
        price=event.price,
        qty=event.qty,
        cum_qty=0,
        prio_seq=prio_seq,
        margin_bps=state.margin_bps,
        lock=lock_val,
        flag=event.flag
    )
    lock_cash(state, event.account, lock_val)

    reports: list[Report] = [Report.accepted(order_id)]

    # R-M1: Matching
    while order.leaves > 0:
        best_opp = None
        if order.side == "BUY":
            asks = get_asks(state)
            for ask in asks:
                if ask.price <= order.price:
                    best_opp = ask
                else:
                    break
        else:  # SELL
            bids = get_bids(state)
            for bid in bids:
                if bid.price >= order.price:
                    best_opp = bid
                else:
                    break
        
        if not best_opp:
            break

        # R-M3: Self-trade prevention
        if best_opp.account == order.account:
            # Cancel resting order
            remove_order(state, best_opp.order_id)
            # Move full lock of resting order to free_cash
            release_lock(state, best_opp.account, best_opp.lock)
            reports.append(Report.cancelled(best_opp.order_id, "STP"))
            continue

        # R-M2: Calculate fill
        fill_qty = min(order.leaves, best_opp.leaves)
        fill_price = best_opp.price
        
        # Identify buyer and seller
        if order.side == "BUY":
            buyer_acc = order.account
            seller_acc = best_opp.account
            buy_oid = order.order_id
            sell_oid = best_opp.order_id
        else:
            buyer_acc = best_opp.account
            seller_acc = order.account
            buy_oid = best_opp.order_id
            sell_oid = order.order_id

        # R-M4: Fill effect
        # 3. Add q to cum_qty
        order.cum_qty += fill_qty
        best_opp.cum_qty += fill_qty

        # 4. Update locks
        # Incoming order lock update
        old_order_lock = order.lock
        new_order_lock = ceil_div(order.leaves - fill_qty if order.leaves > fill_qty else 0, 
                                  order.price * order.margin_bps // 10000 if order.price * order.margin_bps // 10000 > 0 else 1)
        # Wait, Rule R-M4.4 says: new_lock = ceil_div(leaves * order.price * order.margin_bps, 10000)
        # We must use the leaves AFTER the fill (which is order.leaves - fill_qty if we haven't updated it yet)
        # But the rule says "For each of the two orders... compute new_lock".
        # Let's compute it based on the leaves after the update.
        
        # Update order's leaves (implicitly done by updating cum_qty)
        # We need to calculate the delta for the incoming order and the resting order.
        
        # For incoming order (taker)
        new_order_leaves = order.qty - order.cum_qty
        new_order_lock = ceil_div(new_order_leaves * order.price * order.margin_bps, 10000)
        order.lock = new_order_lock
        lock_diff_taker = old_order_lock - new_order_lock
        # Rule says "Move old_lock - new_lock from locked_margin to free_cash". 
        # For the taker, the lock is already in locked_margin.
        release_lock(state, order.account, lock_diff_taker)

        # For resting order (maker)
        old_maker_lock = best_opp.lock
        new_maker_leaves = best_opp.qty - best_opp.cum_qty
        new_maker_lock = ceil_div(new_maker_leaves * best_opp.price * best_opp.margin_bps, 10000)
        best_opp.lock = new_maker_lock
        lock_diff_maker = old_maker_lock - new_maker_lock
        release_lock(state, best_opp.account, lock_diff_maker)

        # 5/6. Settle and report
        fill = Fill(
            buy_order_id=buy_oid,
            sell_order_id=sell_oid,
            price=fill_price,
            qty=fill_qty,
            taker_order_id=order.order_id,
            buyer=buyer_acc,
            seller=seller_acc
        )
        reports.extend(settle_fill(engine, fill))

        # If resting order is full, it is removed from book (R-M4/R-M5)
        if best_opp.leaves == 0:
            remove_order(state, best_opp.order_id)

    # R-B5.6: IOC remainder
    if order.flag == "IOC" and order.leaves > 0:
        reports.append(Report.cancelled(order.order_id, "IOC_REMAINDER"))
        release_lock(state, order.account, order.lock)
    # R-B5.7: Rest remainder
    elif order.leaves > 0:
        add_order(state, order)

    return reports
