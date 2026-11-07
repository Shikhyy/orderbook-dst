# Human audit sheet (blinded)

For each trial decide: does this code correctly implement the task's rules? Judge it
against the task's `instruction.md` only. You do not see the grader's verdict or the
model name. Record verdicts in a JSON file like:

    {"T01": {"verdict": true, "reason": "matches R-M1..R-M5"},
     "T02": {"verdict": false, "reason": "keeps last crossing order, not best"}}

`true` = the code is correct, `false` = it has at least one rule violation.

---

## T01: task `f4_waterfall_b`
Rules: `tasks/f4_waterfall_b/instruction.md`

```python
--- File: exchange_core/handlers/shock.py ---
"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import EngineState
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.config import EngineConfig

def handle_shock(engine: EngineState, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    reports = []
    mark_price = event.mark_price
    accounts = engine.accounts
    cfg = engine.cfg

    # Rule R-W1: Set mark_price and process waterfall for each account except LIQ
    engine.mark_price = mark_price
    reports.append(Report.mark_set(mark_price))

    # Sort accounts by account-id in ascending order, excluding LIQ
    account_ids = sorted([acc_id for acc_id in accounts if acc_id != "LIQ"])

    for acc_id in account_ids:
        account = accounts[acc_id]
        position = account.position
        free_cash = account.free_cash
        locked_margin = account.locked_margin

        # Rule R-W2: Check if account is in breach
        if position != 0:
            avail = free_cash + position * mark_price
            req = ceil_div(abs(position) * mark_price * cfg.MAINT_BPS, 10000)
            in_breach = avail < req

            if in_breach:
                # Rule R-W3: Stage 1 - Cancel all resting orders in ascending prio_seq order
                account_orders = get_account_orders(engine, acc_id)
                account_orders_sorted = sorted(account_orders, key=lambda o: o.prio_seq)

                for order in account_orders_sorted:
                    order_id = order.order_id
                    remove_order(engine, order_id)
                    reports.append(Report.cancelled(order_id=order_id, reason="RISK"))

                # Rule R-W4: Recompute breach after cancelling orders
                account = accounts[acc_id]
                free_cash = account.free_cash
                avail = free_cash + position * mark_price
                req = ceil_div(abs(position) * mark_price * cfg.MAINT_BPS, 10000)
                in_breach_after_stage1 = avail < req

                if in_breach_after_stage1:
                    # Rule R-W5: Stage 2 - Liquidate the whole position
                    liq_account = accounts["LIQ"]
                    qty = position

                    # Update positions
                    accounts[acc_id].position = 0
                    liq_account.position += qty

                    # Transfer cash
                    if qty > 0:
                        # Account sells to LIQ
                        accounts[acc_id].free_cash += qty * mark_price
                        liq_account.free_cash -= qty * mark_price
                    else:
                        # Account buys from LIQ
                        accounts[acc_id].free_cash -= abs(qty) * mark_price
                        liq_account.free_cash += abs(qty) * mark_price

                    reports.append(Report.liquidated(account=acc_id, qty=qty))

    return reports

```

---

## T02: task `f4_waterfall_b`
Rules: `tasks/f4_waterfall_b/instruction.md`

```python
--- File: exchange_core/handlers/shock.py ---
"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from typing import Any

from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Report


def _in_breach(engine: Any, account: Any, mark_price: int) -> bool:
    position = account.position
    if position == 0:
        return False

    avail = account.free_cash + position * mark_price
    required = ceil_div(abs(position) * mark_price * engine.cfg.MAINT_BPS, 10_000)
    return avail < required


def handle_shock(engine: Any, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    state = engine.state
    mark_price = event.mark_price
    state.mark_price = mark_price

    reports: list[Report] = [Report.mark_set(mark_price)]

    for account_id in sorted(state.accounts):
        if account_id == "LIQ":
            continue

        account = state.accounts[account_id]

        if not _in_breach(engine, account, mark_price):
            continue

        # Stage 1: cancel all resting orders in ascending prio_seq order.
        for order in get_account_orders(state, account_id):
            remove_order(state, order.order_id)
            account.free_cash += order.lock
            account.locked_margin -= order.lock
            reports.append(Report.cancelled(order.order_id, "RISK"))

        # Stage 2: liquidate only if still in breach after Stage 1.
        if not _in_breach(engine, account, mark_price):
            continue

        orig_position = account.position
        notional = abs(orig_position) * mark_price
        liq = state.accounts["LIQ"]

        if orig_position > 0:
            # Account sells to LIQ: LIQ pays, account receives.
            liq.free_cash -= notional
            account.free_cash += notional
        else:
            # Account buys from LIQ: account pays, LIQ receives.
            account.free_cash -= notional
            liq.free_cash += notional

        account.position = 0
        liq.position += orig_position
        reports.append(Report.liquidated(account_id, orig_position))

    return reports

```

---

## T03: task `f3_fix_b`
Rules: `tasks/f3_fix_b/instruction.md`

```python
--- File: exchange_core/handlers/fix.py ---
"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import SessionState


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    session_id = event.session

    # R-S1: Create session if not exists (for both FIX_MSG and SESSION_RESET)
    if session_id not in engine.state.sessions:
        engine.state.sessions[session_id] = SessionState(epoch=0, next_seq=1, buffer={})

    session = engine.state.sessions[session_id]

    if event.kind == "SESSION_RESET":
        # R-S8
        session.epoch += 1
        session.next_seq = 1
        session.buffer.clear()
        return [Report.session_reset_done(session_id)]

    elif event.kind == "FIX_MSG":
        # R-S2: Check epoch
        if event.epoch != session.epoch:
            return [Report.discarded("EPOCH")]

        seq = event.seq
        next_seq = session.next_seq

        if seq < next_seq:
            # R-S3
            if event.poss_dup:
                return [Report.discarded("DUPLICATE")]
            else:
                return [Report.discarded("SEQ_TOO_LOW")]

        elif seq == next_seq:
            # R-S4
            reports = []

            # Process current message
            if event.body is not None:
                body_reports = engine.dispatch(event.body)
                reports.extend(body_reports)

            session.next_seq += 1

            # Drain buffer in ascending sequence order
            while session.next_seq in session.buffer:
                buffered_msg = session.buffer.pop(session.next_seq)
                if buffered_msg.body is not None:
                    body_reports = engine.dispatch(buffered_msg.body)
                    reports.extend(body_reports)
                session.next_seq += 1

            return reports

        else:  # seq > next_seq
            # R-S5
            if seq in session.buffer:
                return [Report.discarded("DUPLICATE_BUFFERED")]
            else:
                session.buffer[seq] = event
                return [Report.buffered()]

    else:
        # Unknown event kind
        return []

```

---

## T04: task `f5_basket_b`
Rules: `tasks/f5_basket_b/instruction.md`

```python
--- File: exchange_core/handlers/basket.py ---
"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a BASKET event with all-or-nothing rollback semantics."""
    # R-A2: Take snapshot before processing any legs
    snapshot = engine.state.snapshot()
    
    all_reports = []
    
    for i, leg in enumerate(event.legs):
        # R-A2: Process each leg as a NEW_LIMIT event for the account
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag
        )
        
        leg_reports = engine.dispatch(leg_event)
        
        # Check for leg success based on R-A3
        # An order is "accepted" if it's not rejected.
        # However, the rule R-A3 specifies conditions for success:
        # - IOC succeeds if it's accepted and leaves is 0 (must not have IOC_REMAINDER)
        # - POST_ONLY succeeds if it's accepted (must not cross)
        # - A rejected leg fails.
        
        # Looking at the reports returned by dispatch:
        # If the order was rejected, there should be a REJECTED report.
        # If the order was accepted, there should be an ACCEPTED report.
        # For IOC, if it's not fully filled, it might result in REJECTED or 
        # it might be accepted but have remaining quantity.
        # But the rule says: "An IOC leg succeeds if it is accepted and leaves is 0".
        # If the engine's dispatch for NEW_LIMIT returns any REJECTED report, the leg fails.
        # If it returns ACCEPTED but the order's leaves > 0 for an IOC, it's a failure.
        
        # Actually, per rule R-A3:
        # "An IOC leg succeeds if it is accepted and leaves is 0 after matching (it must not have an IOC_REMAINDER cancellation)."
        # This implies we need to verify the state of the order after the event.
        # But the engine.dispatch returns reports.
        
        # Let's look at the reports. If a leg is REJECTED, it fails.
        # If it is ACCEPTED, we check if it met the specific condition.
        
        # For IOC: must have ACCEPTED and no remaining qty.
        # For POST_ONLY: must have ACCEPTED.
        
        is_accepted = False
        is_rejected = False
        
        # We need to find if there's an ACCEPTED report for this leg.
        # Since it's a single NEW_LIMIT event, we can look at the reports.
        # If the event was a NEW_LIMIT, the ACCEPTED report contains the order_id.
        
        # However, we also need to check if it's an IOC and if it left anything.
        # The rule says "it must not have an IOC_REMAINDER cancellation".
        # In this engine's logic, if an IOC is not fully filled, it is usually 
        # rejected or it's an accepted order that is immediately cancelled.
        
        # Let's check the reports for REJECTED.
        failed = False
        for r in leg_reports:
            if r.kind == "REJECTED":
                failed = True
                break
        
        # If not explicitly rejected, we check the specific R-A3 conditions.
        # R-A3: "An IOC leg succeeds if it is accepted and leaves is 0"
        # This is tricky because dispatch might return multiple reports (fills + accepted).
        # We need to ensure we don't fail just because of FILL reports.
        
        # Let's find if there's an ACCEPTED report.
        accepted_report = None
        for r in leg_reports:
            if r.kind == "ACCEPTED":
                accepted_report = r
                break
        
        if not accepted_report:
            failed = True
        elif leg.flag == "IOC":
            # For IOC, we check if there's any indication of leftovers.
            # The rule says "must not have an IOC_REMAINDER cancellation".
            # Usually, if an IOC is not fully filled, the engine returns 
            # REJECTED or a specific cancellation report.
            # If it's ACCEPTED, but the rule says leaves must be 0, we check the order.
            # But we don't have the order ID easily without the report.
            # The ACCEPTED report has the order_id.
            
            order_id = accepted_report.order_id
            order = engine.state.orders.get(order_id)
            if not order or order.leaves > 0:
                failed = True
                
        if failed:
            # R-A4: If a leg fails, restore snapshot and report basket_rolled_back
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index=i)]
        
        all_reports.extend(leg_reports)

    # R-A5: If all legs succeed, report all leg reports then basket_committed
    all_reports.append(Report.basket_committed())
    return all_reports

```

---

## T05: task `f5_basket_b`
Rules: `tasks/f5_basket_b/instruction.md`

```python
--- File: exchange_core/handlers/basket.py ---
"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report, Order
from exchange_core.book import get_order


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a BASKET event with all-or-nothing rollback semantics."""
    snapshot = engine.state.snapshot()
    reports = []
    
    for i, leg in enumerate(event.legs):
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag
        )
        
        leg_reports = engine.dispatch(leg_event)
        
        # Check for failure
        failed = False
        
        # Rule R-A3: Verify acceptance and success criteria
        accepted = any(r.kind == "ACCEPTED" for r in leg_reports)
        if not accepted:
            failed = True
        else:
            # Must not have specific failures
            # For POST_ONLY: must not cross (rejected)
            # For IOC: must not have REMAINDER (cancelled)
            for r in leg_reports:
                if r.kind == "REJECTED":
                    failed = True
                if r.kind == "CANCELLED" and leg.flag == "IOC":
                    failed = True
            
            # Additional check for IOC: must fill completely
            if not failed and leg.flag == "IOC":
                # Find the order ID from the accepted report
                order_id = next(r.order_id for r in leg_reports if r.kind == "ACCEPTED")
                order = get_order(engine.state, order_id)
                if order is not None and order.leaves > 0:
                    failed = True
                    
        if failed:
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index=i)]
        
        reports.extend(leg_reports)
        
    reports.append(Report.basket_committed())
    return reports

```

---

## T06: task `f1_fee_b`
Rules: `tasks/f1_fee_b/instruction.md`

```python
--- File: exchange_core/handlers/settle.py ---
"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from exchange_core.intmath import round_half_even
from exchange_core.ledger import (
    transfer_cash,
    adjust_position,
    pay_fee,
    pay_rebate,
    add_volume,
)
from exchange_core.types import Fill, Report


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle cash, locks, position, volume, and fees for a fill."""
    cfg = engine.cfg
    state = engine.state

    notional = fill.notional
    buyer = fill.buyer
    seller = fill.seller
    taker_order_id = fill.taker_order_id
    buy_order_id = fill.buy_order_id
    sell_order_id = fill.sell_order_id

    # Determine taker and maker
    if taker_order_id == buy_order_id:
        taker = buyer
        maker = seller
    else:
        taker = seller
        maker = buyer

    # 1. Buyer pays notional, seller receives notional
    transfer_cash(state, buyer, seller, notional)

    # 2. Update positions
    adjust_position(state, buyer, fill.qty)
    adjust_position(state, seller, -fill.qty)

    # 3. Compute taker fee based on taker's volume BEFORE this fill
    taker_volume_before = state.accounts[taker].volume
    fee = _compute_taker_fee(cfg, taker_volume_before, notional)

    # 4. Compute maker rebate
    rebate = round_half_even(notional * cfg.MAKER_REBATE_PPM, cfg.PPM)

    # 5. Taker pays fee, maker receives rebate, vault nets fee - rebate
    pay_fee(state, taker, fee)
    pay_rebate(state, maker, rebate)

    # 6. Update volume for both buyer and seller (after fee computation)
    add_volume(state, buyer, notional)
    add_volume(state, seller, notional)

    # 7. Return FILL report
    return [Report.fill(buy_order_id, sell_order_id, fill.price, fill.qty, taker_order_id)]


def _compute_taker_fee(cfg, volume_before: int, notional: int) -> int:
    """Compute tiered taker fee per R-F2."""
    threshold = cfg.TIER_THRESHOLD
    ppm = cfg.PPM
    t0 = cfg.TAKER_PPM_T0
    t1 = cfg.TAKER_PPM_T1

    if volume_before >= threshold:
        return round_half_even(notional * t1, ppm)
    elif volume_before + notional <= threshold:
        return round_half_even(notional * t0, ppm)
    else:
        below = threshold - volume_before
        above = notional - below
        fee_below = round_half_even(below * t0, ppm)
        fee_above = round_half_even(above * t1, ppm)
        return fee_below + fee_above

```

---

## T07: task `f6_match_b`
Rules: `tasks/f6_match_b/instruction.md`

```python
--- File: exchange_core/handlers/new_limit.py ---
"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Report
from exchange_core.state import EngineState
from exchange_core.book import get_asks, get_bids, best_ask, best_bid, add_order, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import lock_cash, release_lock, get_account, transfer_cash, adjust_position, pay_fee, pay_rebate, add_volume

def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:
    """Process a NEW_LIMIT event."""
    state = engine.state
    cfg = engine.cfg
    reports = []

    # Rule R-B4.1: Check if account exists
    if not get_account(state, event.account):
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # Rule R-B4.2: Validate order parameters
    if event.qty <= 0 or event.price <= 0 or event.price % cfg.tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # Rule R-B4.3: Check POST_ONLY would cross
    if event.flag == "POST_ONLY":
        if event.side == "BUY" and best_ask(state) is not None and best_ask(state) <= event.price:
            return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        if event.side == "SELL" and best_bid(state) is not None and best_bid(state) >= event.price:
            return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # Rule R-B4.4: Check sufficient margin
    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    account = get_account(state, event.account)
    if account.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Rule R-B5.1: Assign order_id and prio_seq
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    # Rule R-B5.2: Create order
    order = type('Order', (), {
        'order_id': order_id,
        'account': event.account,
        'side': event.side,
        'price': event.price,
        'qty': event.qty,
        'cum_qty': 0,
        'prio_seq': prio_seq,
        'margin_bps': state.margin_bps,
        'lock': lock,
        'flag': event.flag
    })

    # Rule R-B5.3: Lock margin
    lock_cash(state, event.account, lock)

    # Rule R-B5.4: Report accepted
    reports.append(Report.accepted(order_id))

    # Rule R-M1 to R-M5: Matching logic
    if event.side == "BUY":
        opposite_orders = get_asks(state)
    else:
        opposite_orders = get_bids(state)

    opposite_orders.sort(key=lambda o: (o.price if event.side == "BUY" else -o.price, o.prio_seq))

    for opposite_order in opposite_orders:
        if event.side == "BUY" and opposite_order.price > event.price:
            break
        if event.side == "SELL" and opposite_order.price < event.price:
            break

        # Rule R-M3: Self-trade prevention
        if opposite_order.account == event.account:
            # Cancel the resting order
            remove_order(state, opposite_order.order_id)
            release_lock(state, opposite_order.account, opposite_order.lock)
            reports.append(Report.cancelled(opposite_order.order_id, "STP"))
            continue

        # Calculate fill quantity
        fill_qty = min(order.leaves, opposite_order.leaves)
        fill_price = opposite_order.price

        # Create fill
        fill = type('Fill', (), {
            'buy_order_id': opposite_order.order_id if event.side == "BUY" else order_id,
            'sell_order_id': order_id if event.side == "BUY" else opposite_order.order_id,
            'price': fill_price,
            'qty': fill_qty,
            'taker_order_id': order_id,
            'buyer': opposite_order.account if event.side == "BUY" else event.account,
            'seller': event.account if event.side == "BUY" else opposite_order.account
        })

        # Process fill
        fill_reports = settle_fill(engine, fill)
        reports.extend(fill_reports)

        # Update order leaves and lock
        order.leaves = order.qty - order.cum_qty - fill_qty
        opposite_order.leaves = opposite_order.qty - opposite_order.cum_qty - fill_qty

        # Update order cum_qty and lock
        order.cum_qty += fill_qty
        opposite_order.cum_qty += fill_qty

        # Update locks
        old_lock_order = order.lock
        old_lock_opposite = opposite_order.lock

        new_lock_order = ceil_div(order.leaves * order.price * order.margin_bps, 10000)
        new_lock_opposite = ceil_div(opposite_order.leaves * opposite_order.price * opposite_order.margin_bps, 10000)

        release_lock(state, event.account, old_lock_order - new_lock_order)
        release_lock(state, opposite_order.account, old_lock_opposite - new_lock_opposite)

        order.lock = new_lock_order
        opposite_order.lock = new_lock_opposite

        # If order is fully filled, remove it from book
        if order.leaves == 0:
            remove_order(state, order_id)
        if opposite_order.leaves == 0:
            remove_order(state, opposite_order.order_id)

    # Rule R-B5.6: Handle IOC remainder
    if event.flag == "IOC" and order.leaves > 0:
        reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
        release_lock(state, event.account, order.lock)

    # Rule R-B5.7: Rest the remainder if not IOC
    elif order.leaves > 0:
        add_order(state, order)

    return reports

```

---

## T08: task `f6_match_b`
Rules: `tasks/f6_match_b/instruction.md`

```python
--- File: exchange_core/handlers/new_limit.py ---
"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Report, Order, Fill
from exchange_core.state import EngineState
from exchange_core.book import get_bids, get_asks, best_bid, best_ask, add_order, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import lock_cash, release_lock, get_account

def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:
    """Process a NEW_LIMIT event."""
    state = engine.state
    cfg = engine.cfg
    reports = []

    # R-B4 Validation
    if not get_account(state, event.account):
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    if event.qty <= 0 or event.price <= 0 or event.price % cfg.tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    if event.flag == "POST_ONLY":
        if event.side == "BUY" and best_ask(state) is not None and best_ask(state) <= event.price:
            return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        if event.side == "SELL" and best_bid(state) is not None and best_bid(state) >= event.price:
            return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    account = get_account(state, event.account)
    if account is None:
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if account.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5 Processing
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    new_order = Order(
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
    reports.append(Report.accepted(order_id))

    # Matching logic
    if event.side == "BUY":
        opposite_orders = get_asks(state)
    else:
        opposite_orders = get_bids(state)

    # Sort opposite orders by price and prio_seq
    opposite_orders.sort(key=lambda o: (o.price, o.prio_seq))

    for opposite_order in opposite_orders:
        if event.side == "BUY" and opposite_order.price > event.price:
            break
        if event.side == "SELL" and opposite_order.price < event.price:
            break

        if event.side == "BUY" and opposite_order.account == event.account:
            # R-M3 Self-trade prevention
            reports.append(Report.cancelled(opposite_order.order_id, "STP"))
            release_lock(state, opposite_order.account, opposite_order.lock)
            remove_order(state, opposite_order.order_id)
            continue

        if event.side == "BUY" and opposite_order.price <= event.price:
            fill_qty = min(new_order.leaves, opposite_order.leaves)
            fill_price = opposite_order.price

            # Create fill
            fill = Fill(
                buy_order_id=opposite_order.order_id,
                sell_order_id=order_id,
                price=fill_price,
                qty=fill_qty,
                taker_order_id=order_id,
                buyer=opposite_order.account,
                seller=event.account
            )

            # Update order leaves and lock
            new_order.cum_qty += fill_qty
            opposite_order.cum_qty += fill_qty

            # Calculate new lock for both orders
            new_order_lock = ceil_div((new_order.qty - new_order.cum_qty) * new_order.price * new_order.margin_bps, 10000)
            new_opposite_lock = ceil_div((opposite_order.qty - opposite_order.cum_qty) * opposite_order.price * opposite_order.margin_bps, 10000)

            # Release old lock and apply new lock
            release_lock(state, event.account, lock - new_order_lock)
            release_lock(state, opposite_order.account, opposite_order.lock - new_opposite_lock)
            lock_cash(state, event.account, new_order_lock)
            lock_cash(state, opposite_order.account, new_opposite_lock)

            # Update order locks
            new_order.lock = new_order_lock
            opposite_order.lock = new_opposite_lock

            # Settle fill
            fill_reports = settle_fill(engine, fill)
            reports.extend(fill_reports)

            # If either order is fully filled, remove it from the book
            if new_order.leaves == 0:
                break
            if opposite_order.leaves == 0:
                remove_order(state, opposite_order.order_id)

        elif event.side == "SELL" and opposite_order.price >= event.price:
            fill_qty = min(new_order.leaves, opposite_order.leaves)
            fill_price = opposite_order.price

            # Create fill
            fill = Fill(
                buy_order_id=opposite_order.order_id,
                sell_order_id=order_id,
                price=fill_price,
                qty=fill_qty,
                taker_order_id=order_id,
                buyer=opposite_order.account,
                seller=event.account
            )

            # Update order leaves and lock
            new_order.cum_qty += fill_qty
            opposite_order.cum_qty += fill_qty

            # Calculate new lock for both orders
            new_order_lock = ceil_div((new_order.qty - new_order.cum_qty) * new_order.price * new_order.margin_bps, 10000)
            new_opposite_lock = ceil_div((opposite_order.qty - opposite_order.cum_qty) * opposite_order.price * opposite_order.margin_bps, 10000)

            # Release old lock and apply new lock
            release_lock(state, event.account, lock - new_order_lock)
            release_lock(state, opposite_order.account, opposite_order.lock - new_opposite_lock)
            lock_cash(state, event.account, new_order_lock)
            lock_cash(state, opposite_order.account, new_opposite_lock)

            # Update order locks
            new_order.lock = new_order_lock
            opposite_order.lock = new_opposite_lock

            # Settle fill
            fill_reports = settle_fill(engine, fill)
            reports.extend(fill_reports)

            # If either order is fully filled, remove it from the book
            if new_order.leaves == 0:
                break
            if opposite_order.leaves == 0:
                remove_order(state, opposite_order.order_id)

    # Handle IOC remainder
    if event.flag == "IOC" and new_order.leaves > 0:
        reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
        release_lock(state, event.account, new_order.lock)
    else:
        if new_order.leaves > 0:
            add_order(state, new_order)

    return reports

```

---

## T09: task `f5_basket_b`
Rules: `tasks/f5_basket_b/instruction.md`

```python
--- File: exchange_core/handlers/basket.py ---
"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a BASKET event with all-or-nothing rollback semantics."""
    # Take a snapshot of the whole engine state before processing any legs
    snapshot = engine.state.snapshot()
    all_reports: list[Report] = []

    # Iterate over each leg in order
    for leg_index, leg in enumerate(event.legs):
        # Build a NEW_LIMIT event for this leg
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag,
            order_id=0,  # let engine generate a new order_id
        )

        # Dispatch the NEW_LIMIT event and get the reports for this leg
        leg_reports = engine.dispatch(leg_event)

        # Check if this leg failed: if the first report is a BASKET_ROLLED_BACK,
        # the engine indicates failure for this leg.
        if leg_reports and leg_reports[0].kind == "BASKET_ROLLED_BACK":
            # Roll back to the snapshot taken before processing any legs
            engine.state.restore(snapshot)
            # Return only the rolled-back report for the failing leg
            return [Report.basket_rolled_back(leg_index)]

        # Leg succeeded – add its reports to the cumulative list
        all_reports.extend(leg_reports)

    # If we processed all legs without failure, commit the basket
    all_reports.append(Report.basket_committed())
    return all_reports

```

---

## T10: task `f2_replace_a`
Rules: `tasks/f2_replace_a/instruction.md`

```python
--- File: exchange_core/rules/replace_rule.py ---
"""exchange_core/rules/replace_rule.py
Pure function for replace decisions.
Rules R-P1, R-P2 (steps 2, 3), and R-P3. Target for task f2_replace_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.types import Order, ReplaceDecision


def decide_replace(
    order: Order,
    new_price: int,
    new_qty: int,
    cfg: EngineConfig,
) -> ReplaceDecision:
    """Decide whether a replace request is valid and whether it keeps priority.

    Rules R-P1, R-P2 (steps 2 and 3), R-P3.
    """
    # R-P2 step 2: Validate new price
    if new_price <= 0 or new_price % cfg.TICK != 0:
        return ReplaceDecision(
            ok=False,
            reason="INVALID_ORDER",
            keep_priority=False,
            new_leaves=0,
        )

    # R-P2 step 3: Validate new quantity against cum_qty
    if new_qty <= order.cum_qty:
        return ReplaceDecision(
            ok=False,
            reason="INVALID_REPLACE",
            keep_priority=False,
            new_leaves=0,
        )

    # Calculate new leaves
    new_leaves = new_qty - order.cum_qty

    # R-P3: Determine priority retention
    # Keep priority if: same price AND new_qty <= old qty
    # (specifically: same price and new_qty < old qty, or same price and same qty)
    if new_price == order.price and new_qty <= order.qty:
        keep_priority = True
    else:
        keep_priority = False

    return ReplaceDecision(
        ok=True,
        reason="",
        keep_priority=keep_priority,
        new_leaves=new_leaves,
    )

```

---

## T11: task `f6_match_b`
Rules: `tasks/f6_match_b/instruction.md`

```python
--- File: exchange_core/handlers/new_limit.py ---
"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Fill, Order, Report
from exchange_core.intmath import ceil_div
from exchange_core.book import add_order, remove_order, get_asks, get_bids


def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a NEW_LIMIT event."""
    state = engine.state
    tick = engine.cfg.tick

    # R-B4.1
    if event.account not in state.accounts:
        return [Report.rejected("UNKNOWN_ACCOUNT")]

    # R-B4.2
    if event.qty <= 0 or event.price <= 0 or event.price % tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-B4.3
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            asks = get_asks(state)
            if asks and asks[0].price <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:
            bids = get_bids(state)
            if bids and bids[0].price >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # R-B4.4
    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    acc = state.accounts[event.account]
    if acc.free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # R-B5.1
    order_id = state.next_order_id
    prio_seq = state.next_prio_seq
    state.next_order_id += 1
    state.next_prio_seq += 1

    # R-B5.2
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
        flag=event.flag,
    )

    # R-B5.3
    acc.free_cash -= lock
    acc.locked_margin += lock

    # R-B5.4
    reports = [Report.accepted(order_id)]

    # R-M1 Matching loop
    while order.leaves > 0:
        if order.side == "BUY":
            candidates = get_asks(state)
            if not candidates or candidates[0].price > order.price:
                break
            best_opp = candidates[0]
        else:
            candidates = get_bids(state)
            if not candidates or candidates[0].price < order.price:
                break
            best_opp = candidates[0]

        # R-M3 STP
        if best_opp.account == order.account:
            remove_order(state, best_opp.order_id)
            opp_acc = state.accounts[best_opp.account]
            opp_acc.free_cash += best_opp.lock
            opp_acc.locked_margin -= best_opp.lock
            reports.append(Report.cancelled(best_opp.order_id, "STP"))
            continue

        # R-M2 Fill
        fill_qty = min(order.leaves, best_opp.leaves)
        fill_price = best_opp.price

        if order.side == "BUY":
            buy_order, sell_order = order, best_opp
        else:
            buy_order, sell_order = best_opp, order

        fill = Fill(
            buy_order_id=buy_order.order_id,
            sell_order_id=sell_order.order_id,
            price=fill_price,
            qty=fill_qty,
            taker_order_id=order.order_id,
            buyer=buy_order.account,
            seller=sell_order.account,
        )

        # R-M4 updates
        # 3. cum_qty
        order.cum_qty += fill_qty
        best_opp.cum_qty += fill_qty

        # 4. new_lock
        # Taker
        old_lock_taker = order.lock
        new_lock_taker = ceil_div(order.leaves * order.price * order.margin_bps, 10000)
        order.lock = new_lock_taker
        acc_taker = state.accounts[order.account]
        acc_taker.locked_margin -= (old_lock_taker - new_lock_taker)
        acc_taker.free_cash += (old_lock_taker - new_lock_taker)

        # Maker
        old_lock_maker = best_opp.lock
        new_lock_maker = ceil_div(best_opp.leaves * best_opp.price * best_opp.margin_bps, 10000)
        best_opp.lock = new_lock_maker
        acc_maker = state.accounts[best_opp.account]
        acc_maker.locked_margin -= (old_lock_maker - new_lock_maker)
        acc_maker.free_cash += (old_lock_maker - new_lock_maker)

        # 5 & 6. Settle and report
        reports.extend(settle_fill(engine, fill))

        # Maker removal if filled
        if best_opp.leaves == 0:
            remove_order(state, best_opp.order_id)

    # R-B5.6 & 5.7
    if order.flag == "IOC" and order.leaves > 0:
        reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
        acc.free_cash += order.lock
        acc.locked_margin -= order.lock
    elif order.leaves > 0:
        add_order(state, order)

    return reports

```

---

## T12: task `f4_waterfall_b`
Rules: `tasks/f4_waterfall_b/instruction.md`

```python
--- File: exchange_core/handlers/shock.py ---
"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from typing import Any
from exchange_core.types import Event, Report
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock, adjust_position, transfer_cash


def handle_shock(engine: Any, event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    # R-W1: Set mark price
    engine.state.mark_price = event.mark_price
    reports: list[Report] = [Report.mark_set(mark_price=event.mark_price)]

    # R-W1: Get accounts except LIQ, sorted by ID ascending
    account_ids = sorted([acc_id for acc_id in engine.state.accounts if acc_id != "LIQ"])

    for acc_id in account_ids:
        acc = engine.state.accounts[acc_id]
        pos = acc.position

        # R-W2: Position 0 is never in breach
        if pos == 0:
            continue

        # Check breach condition
        # avail = free_cash + position * mark_price
        # req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)
        def is_breached(a: Any) -> bool:
            avail = a.free_cash + (a.position * engine.state.mark_price)
            req = ceil_div(abs(a.position) * engine.state.mark_price * engine.cfg.MAINT_BPS, 10000)
            return avail < req

        if not is_breached(acc):
            continue

        # Stage 1: Cancel resting orders
        # R-W3: Cancel in ascending prio_seq order
        orders = get_account_orders(engine.state, acc_id)
        for o in orders:
            # Each cancel releases the lock to free_cash
            # Note: orders in book.py are already filtered by leaves > 0
            # R-W3: reports CANCELLED(order_id, RISK)
            reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))
            # Release the lock associated with this specific order
            # The rule says "Each cancel releases the lock to free_cash"
            # The amount to release is the 'lock' field of the order.
            release_lock(engine.state, acc_id, o.lock)
            remove_order(engine.state, o.order_id)

        # R-W4: Re-compute breach test after Stage 1
        if not is_breached(acc):
            continue

        # Stage 2: Liquidation
        # R-W5: Liquidate whole position at mark_price against LIQ
        orig_position = pos
        mark_price = engine.state.mark_price

        if orig_position > 0:
            # Long: account sells position units to LIQ.
            # Account receives pos * mark_price. LIQ pays.
            notional = orig_position * mark_price
            transfer_cash(engine.state, "LIQ", acc_id, notional)
            adjust_position(engine.state, "LIQ", orig_position)
        else:
            # Short: account buys abs(pos) units from LIQ.
            # Account pays abs(pos) * mark_price. LIQ receives.
            notional = abs(orig_position) * mark_price
            transfer_cash(engine.state, acc_id, "LIQ", notional)
            adjust_position(engine.state, "LIQ", orig_position)

        # Position of account becomes 0
        acc.position = 0
        acc.locked_margin = 0  # Implicitly, no more margin can be locked if position is 0
        # Note: Since we just liquidated, we should ensure any residual lock/free_cash
        # logic is handled. The rules say "position becomes 0". 
        # Since we are in Stage 2, the account was in breach. 
        # After liquidation, pos=0, so req=0. avail = free_cash. 
        # As long as free_cash >= 0, we are fine.
        
        # R-W5: report LIQUIDATED(account, qty)
        reports.append(Report.liquidated(account=acc_id, qty=orig_position))

    return reports

```

---

## T13: task `f1_fee_a`
Rules: `tasks/f1_fee_a/instruction.md`

```python
--- File: exchange_core/rules/fee_rule.py ---
"""exchange_core/rules/fee_rule.py
Pure functions for taker fee and maker rebate calculation.
Rules R-F2 and R-F3. Target for task f1_fee_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import round_half_even


def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic (Rule R-F2)."""
    threshold = cfg.tier_threshold

    if volume_before >= threshold:
        return round_half_even(notional * cfg.taker_ppm_t1, cfg.ppm)

    if volume_before + notional <= threshold:
        return round_half_even(notional * cfg.taker_ppm_t0, cfg.ppm)

    below = threshold - volume_before
    above = notional - below
    fee_below = round_half_even(below * cfg.taker_ppm_t0, cfg.ppm)
    fee_above = round_half_even(above * cfg.taker_ppm_t1, cfg.ppm)
    return fee_below + fee_above


def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill (Rule R-F3)."""
    return round_half_even(notional * cfg.maker_rebate_ppm, cfg.ppm)

```

---

## T14: task `f1_fee_b`
Rules: `tasks/f1_fee_b/instruction.md`

```python
--- File: exchange_core/handlers/settle.py ---
"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3.
"""
from exchange_core.intmath import round_half_even
from exchange_core.types import Fill, Report


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle cash, position, volume, and fees for a fill."""
    cfg = engine.cfg
    state = engine.state

    buyer = state.accounts[fill.buyer]
    seller = state.accounts[fill.seller]

    if fill.taker_order_id == fill.buy_order_id:
        taker = buyer
        maker = seller
    else:
        taker = seller
        maker = buyer

    notional = fill.notional
    ppm = cfg.ppm
    threshold = cfg.tier_threshold

    volume_before = taker.volume

    # 1-2: cash transfer and position update.
    buyer.free_cash -= notional
    buyer.position += fill.qty
    seller.free_cash += notional
    seller.position -= fill.qty

    # 3: taker fee from the taker's pre-fill volume.
    if volume_before >= threshold:
        fee = round_half_even(notional * cfg.taker_ppm_t1, ppm)
    elif volume_before + notional <= threshold:
        fee = round_half_even(notional * cfg.taker_ppm_t0, ppm)
    else:
        below = threshold - volume_before
        above = notional - below
        fee = (
            round_half_even(below * cfg.taker_ppm_t0, ppm)
            + round_half_even(above * cfg.taker_ppm_t1, ppm)
        )

    # 4: maker rebate.
    rebate = round_half_even(notional * cfg.maker_rebate_ppm, ppm)

    # 5: collect fee, pay rebate, update vault.
    taker.free_cash -= fee
    maker.free_cash += rebate
    state.fee_vault += fee - rebate

    # 6: volume updates happen after the current fill's fee is computed.
    buyer.volume += notional
    seller.volume += notional

    # 7: emit exactly one FILL report.
    return [
        Report.fill(
            buy_order_id=fill.buy_order_id,
            sell_order_id=fill.sell_order_id,
            price=fill.price,
            qty=fill.qty,
            taker_order_id=fill.taker_order_id,
        )
    ]

```

---

## T15: task `f5_basket_b`
Rules: `tasks/f5_basket_b/instruction.md`

```python
--- File: exchange_core/handlers/basket.py ---
"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import EngineState
from exchange_core.handlers.new_limit import handle_new_limit

def handle_basket(engine: "Engine", event: Event) -> list[Report]:
    """Process a BASKET event with all-or-nothing rollback semantics."""
    if not event.legs:
        return [Report.basket_committed()]

    # Take a snapshot of the current state
    snapshot = engine.state.snapshot()
    reports = []

    for leg_index, leg in enumerate(event.legs):
        # Create a NEW_LIMIT event for the current leg
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag
        )

        # Process the leg event
        leg_reports = engine.dispatch(leg_event)

        # Check if the leg failed
        if any(report.kind == "REJECTED" for report in leg_reports):
            # Rollback to the snapshot
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index)]

        # Check IOC leg success condition (leaves == 0)
        if leg.flag == "IOC":
            # Check if the leg was fully matched (leaves == 0)
            order_id = leg_reports[0].order_id if leg_reports else 0
            order = engine.state.orders.get(order_id)
            if order and order.leaves != 0:
                # IOC leg not fully matched, rollback
                engine.state.restore(snapshot)
                return [Report.basket_rolled_back(leg_index)]

        # Check POST_ONLY leg success condition (no crossing)
        if leg.flag == "POST_ONLY":
            # Check if the leg would cross the book
            # This is implicitly handled by the engine's rules, but we need to verify
            # that the leg was accepted without crossing
            # Since the engine already processed it, we assume it passed if no REJECTED report
            # and the order is still in the book (not crossing)
            pass

        # Add the leg reports to the basket reports
        reports.extend(leg_reports)

    # If all legs succeeded, commit the basket
    return reports + [Report.basket_committed()]

```

---

## T16: task `f3_fix_a`
Rules: `tasks/f3_fix_a/instruction.md`

```python
--- File: exchange_core/rules/session_rule.py ---
"""exchange_core/rules/session_rule.py
Pure function for FIX session sequence decisions.
Rules R-S1 to R-S5. Target for task f3_fix_a.
"""
from exchange_core.state import SessionState
from exchange_core.types import Event, SessionOutcome, Report


def on_message(session: SessionState, msg: Event) -> SessionOutcome:
    """Process an incoming FIX message according to session sequence rules."""
    # R-S2: Check epoch
    if msg.epoch != session.epoch:
        return SessionOutcome(reports=[Report.discarded("EPOCH")])

    # R-S3: Check seq < next_seq
    if msg.seq < session.next_seq:
        if msg.poss_dup:
            return SessionOutcome(reports=[Report.discarded("DUPLICATE")])
        else:
            return SessionOutcome(reports=[Report.discarded("SEQ_TOO_LOW")])

    # R-S4: seq == next_seq
    if msg.seq == session.next_seq:
        to_process = [msg]
        session.next_seq += 1
        
        # Drain buffer
        while session.next_seq in session.buffer:
            next_msg = session.buffer.pop(session.next_seq)
            to_process.append(next_msg)
            session.next_seq += 1
            
        return SessionOutcome(to_process=to_process)

    # R-S5: seq > next_seq
    if msg.seq > session.next_seq:
        if msg.seq in session.buffer:
            return SessionOutcome(reports=[Report.discarded("DUPLICATE_BUFFERED")])
        else:
            session.buffer[msg.seq] = msg
            return SessionOutcome(reports=[Report.buffered()])

    return SessionOutcome()

```

---

## T17: task `f4_waterfall_b`
Rules: `tasks/f4_waterfall_b/instruction.md`

```python
--- File: exchange_core/handlers/shock.py ---
"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from typing import Any

from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock
from exchange_core.types import Event, Report


def _is_in_breach(account: Any, mark_price: int, maint_bps: int) -> bool:
    if account.position == 0:
        return False
    avail = account.free_cash + account.position * mark_price
    req = ceil_div(abs(account.position) * mark_price * maint_bps, 10000)
    return avail < req


def handle_shock(engine: Any, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    engine.state.mark_price = event.mark_price
    reports: list[Report] = [Report.mark_set(event.mark_price)]

    maint_bps = engine.cfg.MAINT_BPS
    accounts = sorted(acc_id for acc_id in engine.state.accounts if acc_id != "LIQ")

    for acc_id in accounts:
        acc = engine.state.accounts[acc_id]
        if not _is_in_breach(acc, engine.state.mark_price, maint_bps):
            continue

        # Stage 1: Cancel all resting orders of the account
        orders = get_account_orders(engine.state, acc_id)
        for order in orders:
            remove_order(engine.state, order.order_id)
            release_lock(engine.state, acc_id, order.lock)
            reports.append(Report.cancelled(order.order_id, "RISK"))

        # Stage 2: Re-check breach after Stage 1
        if _is_in_breach(acc, engine.state.mark_price, maint_bps):
            orig_position = acc.position
            cash_delta = orig_position * engine.state.mark_price
            acc.free_cash += cash_delta
            acc.position = 0

            liq_acc = engine.state.accounts["LIQ"]
            liq_acc.free_cash -= cash_delta
            liq_acc.position += orig_position

            reports.append(Report.liquidated(acc_id, orig_position))

    return reports

```

---

## T18: task `f2_replace_b`
Rules: `tasks/f2_replace_b/instruction.md`

```python
--- File: exchange_core/handlers/replace.py ---
"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import EngineState
from exchange_core.intmath import ceil_div
from exchange_core.config import EngineConfig
from exchange_core.book import get_order
from exchange_core.ledger import get_account, lock_cash, release_lock

def handle_replace(engine: "Engine", event: Event) -> list[Report]:
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    # Check if order exists
    order_id = event.order_id
    order = get_order(engine.state, order_id)
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    # Check if order is resting (has leaves)
    if order.leaves == 0:
        return [Report.rejected("UNKNOWN_ORDER")]

    # Check new_price validity
    new_price = event.new_price
    new_qty = event.new_qty
    if new_price <= 0 or new_price % engine.cfg.TICK != 0:
        return [Report.rejected("INVALID_ORDER")]

    # Check if new_qty is valid (must be greater than cum_qty)
    if new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    # Check if new price would cross the opposite side of the book
    opposite_side = "SELL" if order.side == "BUY" else "BUY"
    if opposite_side == "BUY":
        best_ask = engine.book.best_ask(engine.state)
    else:
        best_ask = engine.book.best_bid(engine.state)

    if best_ask is not None and (order.side == "BUY" and new_price >= best_ask or order.side == "SELL" and new_price <= best_ask):
        return [Report.rejected("REPLACE_WOULD_CROSS")]

    # Calculate new lock
    new_leaves = new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * new_price * order.margin_bps, 10000)

    # Check if new lock exceeds free cash
    account = get_account(engine.state, order.account)
    if account is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    if new_lock > account.locked_margin + account.free_cash:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Calculate lock difference
    old_lock = order.lock
    lock_diff = new_lock - old_lock

    # Update account cash and lock
    if lock_diff > 0:
        lock_cash(engine.state, order.account, lock_diff)
    elif lock_diff < 0:
        release_lock(engine.state, order.account, -lock_diff)

    # Update order fields
    old_prio_seq = order.prio_seq
    old_price = order.price

    # Determine if priority should be kept
    keep_priority = (new_price == old_price) and (new_qty <= order.qty)

    if keep_priority:
        engine.state.orders[order_id].qty = new_qty
        engine.state.orders[order_id].price = new_price
        engine.state.orders[order_id].lock = new_lock
    else:
        # Update prio_seq and move to back of queue
        engine.state.next_prio_seq += 1
        engine.state.orders[order_id].prio_seq = engine.state.next_prio_seq
        engine.state.orders[order_id].qty = new_qty
        engine.state.orders[order_id].price = new_price
        engine.state.orders[order_id].lock = new_lock

    return [Report.replaced(order_id)]

```

---

## T19: task `f4_waterfall_b`
Rules: `tasks/f4_waterfall_b/instruction.md`

```python
--- File: exchange_core/handlers/shock.py ---
"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import EngineState
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.config import EngineConfig

def handle_shock(engine: Engine, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    reports = []
    state = engine.state
    cfg = engine.cfg

    # Set mark price and add MARK_SET report
    state.mark_price = event.mark_price
    reports.append(Report.mark_set(event.mark_price))

    # Process each account except LIQ in ascending account-id order
    accounts_sorted = sorted(state.accounts.keys())
    for acc_id in accounts_sorted:
        if acc_id == "LIQ":
            continue

        account = state.accounts[acc_id]
        position = account.position
        free_cash = account.free_cash
        mark_price = state.mark_price
        maint_bps = cfg.MAINT_BPS

        # Skip if position is 0 (Rule R-W2)
        if position == 0:
            continue

        # Calculate available cash and maintenance requirement (Rule R-W2)
        avail = free_cash + position * mark_price
        req = ceil_div(abs(position) * mark_price * maint_bps, 10000)

        # Check if account is in breach
        in_breach = avail < req

        if in_breach:
            # Stage 1: Cancel all resting orders in ascending prio_seq order
            account_orders = get_account_orders(state, acc_id)
            for order in account_orders:
                reports.append(Report.cancelled(order.order_id, "RISK"))
                remove_order(state, order.order_id)
                # Release the lock to free_cash
                release_lock(state, acc_id, order.lock)

            # Recalculate available cash after cancelling orders
            avail = free_cash + position * mark_price
            req = ceil_div(abs(position) * mark_price * maint_bps, 10000)

            # Check if account is still in breach after Stage 1
            if avail >= req:
                continue

            # Stage 2: Liquidate the whole position
            qty = position
            reports.append(Report.liquidated(acc_id, qty))

            # Update positions and cash
            adjust_position(state, acc_id, -qty)
            adjust_position(state, "LIQ", qty)
            if qty > 0:
                transfer_cash(state, "LIQ", acc_id, qty * mark_price)
            else:
                transfer_cash(state, acc_id, "LIQ", -qty * mark_price)

    return reports

```

---

## T20: task `f1_fee_b`
Rules: `tasks/f1_fee_b/instruction.md`

```python
--- File: exchange_core/handlers/settle.py ---
"""exchange_core/handlers/settle.py
Settle trades, fees, and volume.
Rules R-M4, R-F1, R-F2, R-F3. Target for task f1_fee_b.
"""
from exchange_core.types import Fill, Report
from exchange_core.intmath import round_half_even


def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:  # type: ignore # noqa: F821
    """Settle cash, locks, position, volume, and fees for a fill."""
    cfg = engine.cfg
    state = engine.state

    notional = fill.price * fill.qty

    # 1. cash transfer notional: buyer pays, seller receives
    state.accounts[fill.buyer].free_cash -= notional
    state.accounts[fill.seller].free_cash += notional

    # 2. position updates
    state.adjust_position(fill.buyer, fill.qty)
    state.adjust_position(fill.seller, -fill.qty)

    # 3. compute taker fee based on taker volume before fill
    order_taker = state.orders[fill.taker_order_id]
    taker_account = order_taker.account
    vol_before = state.accounts[taker_account].volume

    if vol_before >= cfg.TIER_THRESHOLD:
        fee = int(round_half_even(notional * cfg.TAKER_PPM_T1, cfg.PPM))
    elif vol_before + notional <= cfg.TIER_THRESHOLD:
        fee = int(round_half_even(notional * cfg.TAKER_PPM_T0, cfg.PPM))
    else:
        below = cfg.TIER_THRESHOLD - vol_before
        above = notional - below
        fee = int(round_half_even(below * cfg.TAKER_PPM_T0, cfg.PPM)) + int(round_half_even(above * cfg.TAKER_PPM_T1, cfg.PPM))

    # 4. compute maker rebate
    rebate = int(round_half_even(notional * cfg.MAKER_REBATE_PPM, cfg.PPM))

    # 5. fee payment and rebate
    # taker pays fee
    state.pay_fee(taker_account, fee)
    # determine maker account
    if order_taker.account == fill.buyer:
        maker_account = fill.seller
    else:
        maker_account = fill.buyer
    state.pay_rebate(maker_account, rebate)

    # 6. volume update
    state.add_volume(fill.buyer, notional)
    state.add_volume(fill.seller, notional)

    # 7. return report
    return [Report.fill(
        buy_order_id=fill.buy_order_id,
        sell_order_id=fill.sell_order_id,
        price=fill.price,
        qty=fill.qty,
        taker_order_id=fill.taker_order_id,
    )]

```
