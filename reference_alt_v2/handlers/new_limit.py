"""New limit order handler with order matching and execution.

Rules:
- R-B1 to R-B5: Order properties, priority, counters, validation, acceptance, resting/IOC.
- R-M1 to R-M5: Matching priority, fill pricing/quantities, STP, fill accounting, locks.
"""
from typing import Any

from exchange_core.book import add_order, best_ask, best_bid, get_asks, get_bids, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import get_account, has_account, lock_cash, release_lock
from exchange_core.types import Event, Fill, Order, Report

try:
    from exchange_core.handlers.settle import settle_fill
except ImportError:
    from reference_alt_v2.handlers.settle import settle_fill


def handle_new_limit(engine: Any, event: Event) -> list[Report]:
    """Handle a NEW_LIMIT event.

    Rules R-B4, R-B5, R-M1 to R-M5:
    Validation order:
    1. Unknown account -> REJECTED(UNKNOWN_ACCOUNT)
    2. Invalid qty or price -> REJECTED(INVALID_ORDER)
    3. POST_ONLY would cross -> REJECTED(POST_ONLY_WOULD_CROSS)
    4. Insufficient margin -> REJECTED(INSUFFICIENT_MARGIN)

    Acceptance:
    1. Assign order_id and prio_seq from counters.
    2. Store engine.state.margin_bps in order.
    3. Lock cash.
    4. Report ACCEPTED(order_id).
    5. Match order against opposite side:
       - Best price first, lowest prio_seq at same price.
       - Self-trade prevention (STP): cancel resting order with reason STP, release lock, continue.
       - Fill: settle_fill handles cash transfer, position update, and fee settlement.
         Update cum_qty, update locks, report FILL.
       - Filled resting orders removed from book.
    6. If IOC and leaves > 0: cancel remainder (IOC_REMAINDER), release lock.
    7. If not IOC and leaves > 0: add to book.
    """
    # R-B4 Step 1: Account exists
    if not has_account(engine.state, event.account):
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # R-B4 Step 2: Valid qty and price
    if event.qty <= 0 or event.price <= 0 or event.price % engine.cfg.tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-B4 Step 3: POST_ONLY would cross
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            ask_price = best_ask(engine.state)
            if ask_price is not None and event.price >= ask_price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:  # SELL
            bid_price = best_bid(engine.state)
            if bid_price is not None and event.price <= bid_price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # R-B4 Step 4: Insufficient margin
    lock = ceil_div(event.qty * event.price * engine.state.margin_bps, 10000)
    acc = get_account(engine.state, event.account)
    if acc is None or acc.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5 Step 1: Assign counters
    order_id = engine.state.next_order_id
    prio_seq = engine.state.next_prio_seq
    engine.state.next_order_id += 1
    engine.state.next_prio_seq += 1

    # R-B5 Step 2: Store current margin_bps
    margin_bps = engine.state.margin_bps

    # R-B5 Step 3: Lock cash
    lock_cash(engine.state, event.account, lock)

    order = Order(
        order_id=order_id,
        account=event.account,
        side=event.side,
        price=event.price,
        qty=event.qty,
        cum_qty=0,
        prio_seq=prio_seq,
        margin_bps=margin_bps,
        lock=lock,
        flag=event.flag,
    )

    # R-B5 Step 4: Report ACCEPTED
    reports = [Report.accepted(order_id)]

    # R-B5 Step 5: Matching (R-M1 to R-M5)
    while order.leaves > 0:
        if order.side == "BUY":
            candidates = get_asks(engine.state)
            if not candidates or candidates[0].price > order.price:
                break
            resting = candidates[0]
        else:  # SELL
            candidates = get_bids(engine.state)
            if not candidates or candidates[0].price < order.price:
                break
            resting = candidates[0]

        # R-M3: Self-trade prevention (STP)
        if resting.account == order.account:
            remove_order(engine.state, resting.order_id)
            release_lock(engine.state, resting.account, resting.lock)
            resting.lock = 0
            reports.append(Report.cancelled(resting.order_id, "STP"))
            continue

        # R-M2: Fill price and quantity
        fill_price = resting.price
        fill_qty = min(order.leaves, resting.leaves)

        if order.side == "BUY":
            buyer_id, seller_id = order.account, resting.account
            buy_order_id, sell_order_id = order.order_id, resting.order_id
        else:
            buyer_id, seller_id = resting.account, order.account
            buy_order_id, sell_order_id = resting.order_id, order.order_id

        # R-M4 Step 3: Update cum_qty
        order.cum_qty += fill_qty
        resting.cum_qty += fill_qty

        # R-M4 Step 4 & R-M5: Update locks
        order_new_lock = ceil_div(order.leaves * order.price * order.margin_bps, 10000)
        release_lock(engine.state, order.account, order.lock - order_new_lock)
        order.lock = order_new_lock

        resting_new_lock = ceil_div(resting.leaves * resting.price * resting.margin_bps, 10000)
        release_lock(engine.state, resting.account, resting.lock - resting_new_lock)
        resting.lock = resting_new_lock

        # R-M4 Steps 1, 2, 5: Settle cash, positions, fees, rebates, volume
        fill = Fill(
            buy_order_id=buy_order_id,
            sell_order_id=sell_order_id,
            price=fill_price,
            qty=fill_qty,
            taker_order_id=order.order_id,
            buyer=buyer_id,
            seller=seller_id,
        )
        settle_fill(engine, fill)

        # R-M4 Step 6: Report FILL
        reports.append(
            Report.fill(buy_order_id, sell_order_id, fill_price, fill_qty, order.order_id)
        )

        # Fully filled resting order leaves the book
        if resting.leaves == 0:
            remove_order(engine.state, resting.order_id)

    # R-B5 Step 6: IOC remainder cancel
    if order.flag == "IOC" and order.leaves > 0:
        release_lock(engine.state, order.account, order.lock)
        order.lock = 0
        reports.append(Report.cancelled(order.order_id, "IOC_REMAINDER"))
    # R-B5 Step 7: Resting order added to book
    elif order.flag != "IOC" and order.leaves > 0:
        add_order(engine.state, order)

    return reports
