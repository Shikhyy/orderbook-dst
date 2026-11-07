"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Report, Order, Fill
from exchange_core.state import EngineState
from exchange_core.intmath import ceil_div
from exchange_core.book import get_asks, get_bids, best_ask, best_bid, add_order, remove_order
from exchange_core.ledger import lock_cash, release_lock


def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    state: EngineState = engine.state

    # 1. Validation
    if event.account not in state.accounts:
        return [Report.rejected("UNKNOWN_ACCOUNT")]
    if event.qty <= 0 or event.price <= 0 or (event.price % engine.cfg.tick) != 0:
        return [Report.rejected("INVALID_ORDER")]

    # Rule R-B4.3 POST_ONLY check
    if event.flag == "POST_ONLY":
        would_match = False
        if event.side == "BUY":
            ba = best_ask(state)
            if ba is not None and ba <= event.price:
                would_match = True
        elif event.side == "SELL":
            bb = best_bid(state)
            if bb is not None and bb >= event.price:
                would_match = True
        if would_match:
            return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if state.accounts[event.account].free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # 2. Preparation
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    incoming = Order(
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
    reports = [Report.accepted(order_id)]

    # 3. Matching
    leaves = incoming.qty
    while leaves > 0:
        book = get_asks(state) if incoming.side == "BUY" else get_bids(state)
        if not book:
            break
        
        top = book[0]
        # Match condition: R-M1
        if incoming.side == "BUY" and top.price > incoming.price: break
        if incoming.side == "SELL" and top.price < incoming.price: break
        
        # Self-Trade Prevention: R-M3
        if top.account == incoming.account:
            remove_order(state, top.order_id)
            release_lock(state, top.account, top.lock)
            reports.append(Report.cancelled(top.order_id, "STP"))
            continue
            
        # Fill: R-M2, R-M4
        q = min(leaves, top.leaves)
        fill = Fill(
            buy_order_id=incoming.order_id if incoming.side == "BUY" else top.order_id,
            sell_order_id=top.order_id if incoming.side == "BUY" else incoming.order_id,
            price=top.price,
            qty=q,
            taker_order_id=incoming.order_id,
            buyer=incoming.account if incoming.side == "BUY" else top.account,
            seller=top.account if incoming.side == "BUY" else incoming.account
        )
        
        # Update orders for R-M4
        for o in [incoming, top]:
            old_lock = o.lock
            o.cum_qty += q
            new_lock = ceil_div(o.leaves * o.price * o.margin_bps, 10000)
            release_lock(state, o.account, old_lock - new_lock)
            o.lock = new_lock
            
        leaves -= q
        reports.extend(settle_fill(engine, fill))
        
        if top.leaves == 0:
            remove_order(state, top.order_id)

    # 4. Finalize
    if leaves > 0:
        if incoming.flag == "IOC":
            release_lock(state, incoming.account, incoming.lock)
            reports.append(Report.cancelled(incoming.order_id, "IOC_REMAINDER"))
        else:
            incoming.cum_qty = incoming.qty - leaves
            add_order(state, incoming)
            
    return reports
