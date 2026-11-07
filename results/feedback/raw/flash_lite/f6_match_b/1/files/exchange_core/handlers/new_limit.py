"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Report, Order, Fill
from exchange_core.intmath import ceil_div
from exchange_core import book, ledger

def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore
    state = engine.state

    # R-B4.1: Account existence
    if event.account not in state.accounts:
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # R-B4.2: Field validation
    if event.qty <= 0 or event.price <= 0 or (event.price % engine.cfg.tick) != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-B4.3: Post-only check
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            best_ask = book.best_ask(state)
            if best_ask is not None and best_ask <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        elif event.side == "SELL":
            best_bid = book.best_bid(state)
            if best_bid is not None and best_bid >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # R-B4.4: Margin validation
    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if state.accounts[event.account].free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5.1-4: Setup and accept
    oid = state.next_order_id
    pseq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1
    
    new_order = Order(
        order_id=oid, account=event.account, side=event.side, price=event.price,
        qty=event.qty, cum_qty=0, prio_seq=pseq, margin_bps=state.margin_bps,
        lock=lock, flag=event.flag
    )
    
    ledger.lock_cash(state, event.account, lock)
    reports = [Report.accepted(oid)]

    # R-M1-M5: Matching
    while new_order.leaves > 0:
        resting = None
        if new_order.side == "BUY":
            asks = book.get_asks(state)
            if asks and asks[0].price <= new_order.price:
                resting = asks[0]
        else:
            bids = book.get_bids(state)
            if bids and bids[0].price >= new_order.price:
                resting = bids[0]
        
        if not resting:
            break
            
        # R-M3: Self-trade
        if resting.account == new_order.account:
            book.remove_order(state, resting.order_id)
            ledger.release_lock(state, resting.account, resting.lock)
            reports.append(Report.cancelled(resting.order_id, "STP"))
            continue

        # R-M2: Fill
        q = min(new_order.leaves, resting.leaves)
        fill = Fill(
            buy_order_id=new_order.order_id if new_order.side == "BUY" else resting.order_id,
            sell_order_id=resting.order_id if new_order.side == "BUY" else new_order.order_id,
            price=resting.price, qty=q, taker_order_id=new_order.order_id,
            buyer=new_order.account if new_order.side == "BUY" else resting.account,
            seller=resting.account if new_order.side == "BUY" else new_order.account
        )
        
        # R-M4: Settlement
        reports.extend(settle_fill(engine, fill))
        
        for o in [new_order, resting]:
            o.cum_qty += q
            old_lock = o.lock
            new_l = ceil_div(o.leaves * o.price * o.margin_bps, 10000)
            ledger.release_lock(state, o.account, old_lock - new_l)
            o.lock = new_l
            
        if resting.leaves == 0:
            book.remove_order(state, resting.order_id)

    # R-B5.6-7: Remainder
    if new_order.leaves > 0:
        if new_order.flag == "IOC":
            ledger.release_lock(state, new_order.account, new_order.lock)
            reports.append(Report.cancelled(new_order.order_id, "IOC_REMAINDER"))
        else:
            book.add_order(state, new_order)
            
    return reports
