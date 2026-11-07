"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Report, Order, Fill
from exchange_core.state import EngineState
from exchange_core.intmath import ceil_div
from exchange_core.book import get_bids, get_asks, add_order, remove_order
from exchange_core.ledger import lock_cash, release_lock

def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    state: EngineState = engine.state
    
    # R-B4.1
    if event.account not in state.accounts:
        return [Report.rejected("UNKNOWN_ACCOUNT")]
    
    # R-B4.2
    if event.qty <= 0 or event.price <= 0 or (event.price % engine.cfg.tick != 0):
        return [Report.rejected("INVALID_ORDER")]
        
    # R-B4.3 POST_ONLY
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            best = get_asks(state)
            if best and best[0].price <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:
            best = get_bids(state)
            if best and best[0].price >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
    
    # R-B4.4 Margin
    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if state.accounts[event.account].free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]
        
    # R-B5
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1
    
    order = Order(
        order_id=order_id, account=event.account, side=event.side,
        price=event.price, qty=event.qty, cum_qty=0,
        prio_seq=prio_seq, margin_bps=state.margin_bps, lock=lock, flag=event.flag
    )
    
    lock_cash(state, event.account, lock)
    reports = [Report.accepted(order_id)]
    
    # R-M1 to R-M5: Matching
    while order.leaves > 0:
        targets = get_asks(state) if event.side == "BUY" else get_bids(state)
        if not targets:
            break
        best = targets[0]
        
        # Stop if no cross
        if event.side == "BUY" and best.price > order.price:
            break
        if event.side == "SELL" and best.price < order.price:
            break
            
        # R-M3: STP
        if best.account == event.account:
            remove_order(state, best.order_id)
            release_lock(state, best.account, best.lock)
            reports.append(Report.cancelled(best.order_id, "STP"))
            continue
            
        # R-M2/M4: Fill
        q = min(order.leaves, best.leaves)
        fill = Fill(
            buy_order_id=order_id if event.side == "BUY" else best.order_id,
            sell_order_id=best.order_id if event.side == "BUY" else order_id,
            price=best.price, qty=q, taker_order_id=order_id,
            buyer=event.account if event.side == "BUY" else best.account,
            seller=best.account if event.side == "BUY" else event.account
        )
        
        # R-M4.3, 4.4, 4.6
        for o in [order, best]:
            old_lock = o.lock
            o.cum_qty += q
            new_lock = ceil_div(o.leaves * o.price * o.margin_bps, 10000)
            release_lock(state, o.account, old_lock - new_lock)
            o.lock = new_lock
            
        if best.leaves == 0:
            remove_order(state, best.order_id)
        
        reports.extend(settle_fill(engine, fill))
        
    # Final Resting/IOC
    if order.leaves > 0:
        if event.flag == "IOC":
            release_lock(state, order.account, order.lock)
            reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
        else:
            add_order(state, order)
    else:
        # If fully filled, release any final lock (should be 0)
        release_lock(state, order.account, order.lock)
        
    return reports
