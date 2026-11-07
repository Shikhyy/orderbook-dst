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

    # R-B4.1 Account validation
    acc_obj = get_account(state, event.account)
    if acc_obj is None:
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # R-B4.2 Parameter validation
    if event.qty <= 0 or event.price <= 0 or event.price % tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-B4.3 POST_ONLY validation
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            asks = get_asks(state)
            if asks and asks[0].price <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:  # SELL
            bids = get_bids(state)
            if bids and bids[0].price >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # R-B4.4 Margin validation
    lock_val = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if acc_obj.free_cash < lock_val:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5.1 Assign IDs
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    # R-B5.2 Create Order
    # Note: leaves is calculated via property in Order dataclass
    new_order = Order(
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

    # R-B5.3 Margin reservation
    lock_cash(state, event.account, lock_val)

    # R-B5.4 Report Accepted
    reports: list[Report] = [Report.accepted(order_id)]

    # R-M1. Matching logic
    while new_order.leaves > 0:
        if new_order.side == "BUY":
            candidates = get_asks(state)
            # Check if best candidate crosses limit
            if not candidates or candidates[0].price > new_order.price:
                break
            resting = candidates[0]
        else:  # SELL
            candidates = get_bids(state)
            # Check if best candidate crosses limit
            if not candidates or candidates[0].price < new_order.price:
                break
            resting = candidates[0]

        # R-M3. Self-trade prevention
        if resting.account == new_order.account:
            # Cancel resting order
            remove_order(state, resting.order_id)
            # Move full lock of resting order from locked_margin to free_cash
            release_lock(state, resting.account, resting.lock)
            reports.append(Report.cancelled(resting.order_id, "STP"))
            continue

        # R-M2. Determine fill
        fill_qty = min(new_order.leaves, resting.leaves)
        fill_price = resting.price

        # Prepare Fill for settle_fill
        if new_order.side == "BUY":
            fill_data = Fill(
                buy_order_id=new_order.order_id,
                sell_order_id=resting.order_id,
                price=fill_price,
                qty=fill_qty,
                taker_order_id=new_order.order_id,
                buyer=new_order.account,
                seller=resting.account
            )
        else:
            fill_data = Fill(
                buy_order_id=resting.order_id,
                sell_order_id=new_order.order_id,
                price=fill_price,
                qty=fill_qty,
                taker_order_id=new_order.order_id,
                buyer=resting.account,
                seller=new_order.account
            )

        # R-M4. Effect of fill
        # We must update cum_qty and locks manually for R-M4 logic before/during settlement
        # Actually R-M4.3 and R-M4.4 are about the state change in the orders
        # R-M4.1, 2, 5, 6 are handled by settle_fill
        
        # We update cum_qty for the orders in state first so settle_fill sees them or works correctly
        # But R-M4 says: 1, 2 (settle), 3 (cum_qty), 4 (locks), 5, 6 (settle)
        # The instruction says "settle_fill... does not touch cum_qty, locks or the book"
        # So the handler MUST update them.
        
        old_new_lock = new_order.lock
        old_rest_lock = resting.lock
        
        new_order.cum_qty += fill_qty
        resting.cum_qty += fill_qty
        
        # R-M4.4 & R-M5: Update locks
        new_lock_val = ceil_div(new_order.leaves * new_order.price * new_order.margin_bps, 10000)
        rest_lock_val = ceil_div(resting.leaves * resting.price * resting.margin_bps, 10000)
        
        # Update order fields
        new_order.lock = new_lock_val
        resting.lock = rest_lock_val
        
        # Move difference in locks from locked_margin to free_cash
        # Using release_lock/lock_cash is tricky if we want to do (old-new)
        # A direct calculation on the account is safer for "Move old_lock - new_lock"
        # where old_lock is the lock BEFORE the qty increment (which corresponds to the lock of the remaining leaves)
        # Wait, R-M4.4 says: "new_lock = ceil_div(leaves * order.price * order.margin_bps, 10000)".
        # "leaves" here refers to the leaves AFTER the fill.
        
        # Let's re-read R-M4.4 carefully:
        # "new_lock = ceil_div(leaves * order.price * order.margin_bps, 10000), using the margin_bps stored in that order."
        # "Move old_lock - new_lock from locked_margin to free_cash."
        # For the incoming order, 'leaves' decreases, so new_lock < old_lock. 
        # For the resting order, 'leaves' decreases, so new_lock < old_lock.
        # Therefore old_lock - new_lock is positive, and we move it from locked to free.
        
        # To avoid confusion, let's calculate delta based on leaves BEFORE and AFTER fill.
        # But the 'lock' stored in the order is actually the lock of its CURRENT leaves.
        # At the start of the loop, new_order.lock is the lock for its current leaves.
        # After cum_qty += fill_qty, new_order.leaves changes.
        
        # Let's track the "old_lock" before updating cum_qty.
        # However, R-M4 says: 1. Pay, 2. Receive, 3. Add cum_qty, 4. Compute new_lock & move delta.
        # This implies old_lock in R-M4.4 refers to the lock of the order before the fill.
        
        # Correct sequence for R-M4:
        # 3. For each order, add q to cum_qty.
        # 4. For each order, compute new_lock = ceil_div(leaves * ...)
        #    Move old_lock - new_lock from locked_margin to free_cash.
        #    old_lock is the lock before the fill (the lock of the previous leaves).
        
        # Since we already updated new_order.cum_qty, 'leaves' is now the new leaves.
        # But R-M4.4 asks for 'old_lock - new_lock'.
        # Let's use the lock values we stored before updating the orders.
        
        delta_new = old_new_lock - new_lock_val
        delta_rest = old_rest_lock - rest_lock_val
        
        # Update orders in state if they are resting
        if resting.order_id in state.orders:
            state.orders[resting.order_id] = resting
        
        # Update incoming order in local variable (it's not in state yet)
        # (new_order is a local object)
        
        # Apply lock movements
        # For new_order
        acc_new = get_account(state, new_order.account)
        acc_new.locked_margin -= delta_new
        acc_new.free_cash += delta_new
        
        # For resting order
        acc_rest = get_account(state, resting.account)
        acc_rest.locked_margin -= delta_rest
        acc_rest.free_cash += delta_rest
        
        # R-M4.5, 6: Settle and Report
        fill_reports = settle_fill(engine, fill_data)
        reports.extend(fill_reports)

        # If resting is filled, remove it
        if resting.leaves == 0:
            remove_order(state, resting.order_id)

    # R-B5.6. IOC remainder handling
    if new_order.flag == "IOC" and new_order.leaves > 0:
        reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
        # Release the lock: move from locked_margin to free_cash
        release_lock(state, new_order.account, new_order.lock)
    # R-B5.7. Resting remainder
    elif new_order.leaves > 0:
        add_order(state, new_order)

    return reports
