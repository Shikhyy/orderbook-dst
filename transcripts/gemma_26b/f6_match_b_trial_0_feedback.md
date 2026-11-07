# gemma_26b · f6_match_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemma-4-26b-a4b-it` / `None` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | feedback_loop |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 18676 / 3729 |
| Latency (s) | 198.84294509887695 |
| Stop reason | – |
| Timestamp | 2026-11-06T07:13:27.374800+00:00 |
| Prompt | [`prompt.txt`](../../results/feedback/raw/gemma_26b/f6_match_b/0/prompt.txt) (sha256 `75d7ddadb330c7af…`) |
| Raw files | [`results/feedback/raw/gemma_26b/f6_match_b/0/`](../../results/feedback/raw/gemma_26b/f6_match_b/0) |

## Feedback-loop turns

| Turn | Score | Passed | First failure |
|---|---|---|---|
| 0 | 0.225 | False | D1 event 12 report differs from reference |
| 1 | 1.0 | True | –  |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f6_match_b/new_limit.py
+++ model/exchange_core/handlers/new_limit.py
@@ -1,55 +1,53 @@
 """exchange_core/handlers/new_limit.py
-Handle NEW_LIMIT event and execute order matching.
-Rules R-B1 to R-B5, R-M1 to R-M4. Reference only. Matching lives here.
+Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
+Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
 """
-from exchange_core.book import add_order, best_ask, best_bid, get_asks, get_bids, remove_order
+from typing import Any
 from exchange_core.handlers.settle import settle_fill
+from exchange_core.types import Event, Report, Order, Fill
 from exchange_core.intmath import ceil_div
-from exchange_core.types import Event, Fill, Order, Report
+from exchange_core.book import get_asks, get_bids, add_order, remove_order
+from exchange_core.ledger import lock_cash, release_lock, get_account
 
 
 def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process a NEW_LIMIT event.
-
-    Rules R-B4, R-B5, R-M1, R-M2, R-M3, R-M4.
-    """
+    """Process a NEW_LIMIT event."""
     state = engine.state
     cfg = engine.cfg
-    reports: list[Report] = []
 
-    # Rule R-B4 step 1: unknown account check
-    if event.account not in state.accounts:
+    # R-B4.1: Account existence
+    acc_obj = get_account(state, event.account)
+    if acc_obj is None:
         return [Report.rejected("UNKNOWN_ACCOUNT")]
 
-    # Rule R-B4 step 2: invalid order checks
+    # R-B4.2: Invalid order
     if event.qty <= 0 or event.price <= 0 or event.price % cfg.tick != 0:
         return [Report.rejected("INVALID_ORDER")]
 
-    # Rule R-B4 step 3: POST_ONLY crossing check
+    # R-B4.3: POST_ONLY crossing check
     if event.flag == "POST_ONLY":
-        ask, bid = best_ask(state), best_bid(state)
-        if (event.side == "BUY" and ask is not None and ask <= event.price) or (
-            event.side == "SELL" and bid is not None and bid >= event.price
-        ):
-            return [Report.rejected("POST_ONLY_WOULD_CROSS")]
+        if event.side == "BUY":
+            asks = get_asks(state)
+            if asks and asks[0].price <= event.price:
+                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
+        else:
+            bids = get_bids(state)
+            if bids and bids[0].price >= event.price:
+                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
 
-    # Rule R-B4 step 4: margin check
-    acc = state.accounts[event.account]
-    lock = ceil_div(event.qty * event.price * state.margin_bps, 10_000)
-    if acc.free_cash < lock:
+    # R-B4.4: Margin check
+    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
+    if acc_obj.free_cash < lock:
         return [Report.rejected("INSUFFICIENT_MARGIN")]
 
-    # Rule R-B5 step 1: assign order_id and prio_seq from counters
+    # R-B5.1: Assign IDs
     order_id = state.next_order_id
     prio_seq = state.next_prio_seq
     state.next_order_id += 1
     state.next_prio_seq += 1
 
-    # Rule R-B5 step 2 & 3: create order, store engine margin_bps, lock margin
-    acc.free_cash -= lock
-    acc.locked_margin += lock
-
-    order = Order(
+    # R-B5.2 & R-B5.3: Create order and lock margin
+    incoming_order = Order(
         order_id=order_id,
         account=event.account,
         side=event.side,
@@ -59,91 +57,93 @@
         prio_seq=prio_seq,
         margin_bps=state.margin_bps,
         lock=lock,
-        flag=event.flag,
+        flag=event.flag
     )
+    lock_cash(state, event.account, lock)
 
-    # Rule R-B5 step 4: report ACCEPTED
-    reports.append(Report.accepted(order_id))
+    reports: list[Report] = [Report.accepted(order_id)]
 
-    # Rule R-B5 step 5: match the order (Rules R-M1 to R-M4)
-    while order.leaves > 0:
-        # Rule R-M1: find best candidate resting order
-        resting_candidates = get_asks(state) if order.side == "BUY" else get_bids(state)
-        if not resting_candidates:
+    # R-M1: Matching
+    while incoming_order.leaves > 0:
+        best_opp = None
+        if incoming_order.side == "BUY":
+            opp_orders = get_asks(state)
+            if opp_orders and opp_orders[0].price <= incoming_order.price:
+                best_opp = opp_orders[0]
+        else:
+            opp_orders = get_bids(state)
+            if opp_orders and opp_orders[0].price >= incoming_order.price:
+                best_opp = opp_orders[0]
+        
+        if not best_opp:
             break
 
-        best_resting = resting_candidates[0]
-
-        # Check price crossing condition
-        if order.side == "BUY" and best_resting.price > order.price:
-            break
-        if order.side == "SELL" and best_resting.price < order.price:
-            break
-
-        # Rule R-M3: Self-Trade Prevention
-        if best_resting.account == order.account:
-            remove_order(state, best_resting.order_id)
-            # Release resting order lock back to account free_cash
-            state.accounts[best_resting.account].locked_margin -= best_resting.lock
-            state.accounts[best_resting.account].free_cash += best_resting.lock
-            reports.append(Report.cancelled(best_resting.order_id, "STP"))
+        # R-M3: Self-trade prevention
+        if best_opp.account == incoming_order.account:
+            remove_order(state, best_opp.order_id)
+            release_lock(state, best_opp.account, best_opp.lock)
+            reports.append(Report.cancelled(best_opp.order_id, "STP"))
             continue
 
-        # Rule R-M2: fill price is resting price; fill quantity is min(leaves)
-        fill_price = best_resting.price
-        fill_qty = min(order.leaves, best_resting.leaves)
+        # R-M2: Calculate fill
+        fill_qty = min(incoming_order.leaves, best_opp.leaves)
+        fill_price = best_opp.price
 
-        # Rule R-M4 step 3 & 4: adjust cum_qty and locks for both orders
-        # 1. Update maker (resting order)
-        maker_old_lock = best_resting.lock
-        best_resting.cum_qty += fill_qty
-        maker_new_lock = ceil_div(
-            best_resting.leaves * best_resting.price * best_resting.margin_bps, 10_000
-        )
-        maker_release = maker_old_lock - maker_new_lock
-        state.accounts[best_resting.account].locked_margin -= maker_release
-        state.accounts[best_resting.account].free_cash += maker_release
-        best_resting.lock = maker_new_lock
+        if incoming_order.side == "BUY":
+            buyer_acc = incoming_order.account
+            seller_acc = best_opp.account
+            buy_id = incoming_order.order_id
+            sell_id = best_opp.order_id
+        else:
+            buyer_acc = best_opp.account
+            seller_acc = incoming_order.account
+            buy_id = best_opp.order_id
+            sell_id = incoming_order.order_id
 
-        # 2. Update taker (incoming order)
-        taker_old_lock = order.lock
-        order.cum_qty += fill_qty
-        taker_new_lock = ceil_div(order.leaves * order.price * order.margin_bps, 10_000)
-        taker_release = taker_old_lock - taker_new_lock
-        state.accounts[order.account].locked_margin -= taker_release
-        state.accounts[order.account].free_cash += taker_release
-        order.lock = taker_new_lock
-
-        # Remove maker from book if fully filled (leaves == 0)
-        if best_resting.leaves == 0:
-            remove_order(state, best_resting.order_id)
-
-        # Build fill record
-        is_buy = order.side == "BUY"
         fill = Fill(
-            buy_order_id=order.order_id if is_buy else best_resting.order_id,
-            sell_order_id=best_resting.order_id if is_buy else order.order_id,
+            buy_order_id=buy_id,
+            sell_order_id=sell_id,
             price=fill_price,
             qty=fill_qty,
-            taker_order_id=order.order_id,
-            buyer=order.account if is_buy else best_resting.account,
-            seller=best_resting.account if is_buy else order.account,
+            taker_order_id=incoming_order.order_id,
+            buyer=buyer_acc,
+            seller=seller_acc
         )
 
-        # Rule R-M4 steps 1, 2, 5, 6: settle fill financial effects
+        # R-M4: Update cum_qty and locks
+        incoming_order.cum_qty += fill_qty
+        best_opp.cum_qty += fill_qty
+
+        # Update locks (R-M4.4 / R-M5)
+        # Incoming order lock update
+        old_inc_lock = incoming_order.lock
+        new_inc_lock = ceil_div(incoming_order.leaves * incoming_order.price * incoming_order.margin_bps, 10000)
+        diff_inc = old_inc_lock - new_inc_lock
+        if diff_inc > 0:
+            release_lock(state, incoming_order.account, diff_inc)
+        incoming_order.lock = new_inc_lock
+
+        # Best opp lock update
+        old_opp_lock = best_opp.lock
+        new_opp_lock = ceil_div(best_opp.leaves * best_opp.price * best_opp.margin_bps, 10000)
+        diff_opp = old_opp_lock - new_opp_lock
+        if diff_opp > 0:
+            release_lock(state, best_opp.account, diff_opp)
+        best_opp.lock = new_opp_lock
+
+        # R-M4.5/6: Settle and report
         fill_reports = settle_fill(engine, fill)
         reports.extend(fill_reports)
 
-    # Rule R-B5 step 6: IOC remainder handling
-    if order.flag == "IOC" and order.leaves > 0:
-        # Cancel remainder and release lock
-        remaining_lock = order.lock
-        state.accounts[order.account].locked_margin -= remaining_lock
-        state.accounts[order.account].free_cash += remaining_lock
-        order.lock = 0
-        reports.append(Report.cancelled(order.order_id, "IOC_REMAINDER"))
-    elif order.flag != "IOC" and order.leaves > 0:
-        # Rule R-B5 step 7: add resting order to book
-        add_order(state, order)
+        if best_opp.leaves == 0:
+            remove_order(state, best_opp.order_id)
+
+    # R-B5.6 & R-B5.7: Post-match handling
+    if incoming_order.leaves > 0:
+        if incoming_order.flag == "IOC":
+            release_lock(state, incoming_order.account, incoming_order.lock)
+            reports.append(Report.cancelled(incoming_order.order_id, "IOC_REMAINDER"))
+        else:
+            add_order(state, incoming_order)
 
     return reports
```

## Author analysis

_Write after reading the reply: what the model got wrong and why, or whether the grader rejected a valid answer._

## Model reply (verbatim)

````text
<thought>*   Task: Implement `handle_new_limit` in `exchange_core/handlers/new_limit.py`.
    *   Rules: R-B3, R-B4, R-B5, R-M1 to R-M5.
    *   Validation (R-B4):
        1. Account exists?
        2. `qty > 0`, `price > 0`, `price % tick == 0`?
        3. `POST_ONLY` cross check?
        4. `lock = ceil_div(qty * price * state.margin_bps, 10000)`. Enough `free_cash`?
    *   Execution (R-B5):
        1. Assign `order_id`, `prio_seq`, increment counters.
        2. Create `Order`.
        3. Subtract `lock` from `free_cash`, add to `locked_margin`, store in `order.lock`.
        4. Report `ACCEPTED`.
        5. Match (R-M1 to R-M4).
        6. If `IOC` and `leaves > 0`: cancel remainder, release lock, don't store in `state.orders`.
        7. If not `IOC` and `leaves > 0`: store in `state.orders`.
    *   Matching (R-M1 to R-M4):
        - R-M1: BUY matches SELL `price <= limit`. SELL matches BUY `price >= limit`. Best price first, then lowest `prio_seq`.
        - R-M2: Fill price = resting order price. Fill quantity = `min(leaves1, leaves2)`.
        - R-M3: Self-trade prevention (STP). Cancel resting order, release its lock, report `CANCELLED("STP")`, continue matching.
        - R-M4: Effect of fill.
            1. Buyer pays, seller receives (Done by `settle_fill`).
            2. `cum_qty` updated for both (Done by handler).
            3. Lock update: `new_lock = ceil_div(leaves * price * margin_bps, 10000)`. `move = old_lock - new_lock` from `locked_margin` to `free_cash`.
            4. Settle fees (Done by `settle_fill`).
            5. Report fill (Done by `settle_fill`).

    *   The instruction "compute `new_lock = ceil_div(leaves * order.price * order.margin_bps, 10000)`" refers to the *remaining* leaves.
    *   Wait, let's look at R-M4.4 closely: "For each of the two orders, compute `new_lock = ceil_div(leaves * order.price * order.margin_bps, 10000)`, using the `margin_bps` stored in that order. Move `old_lock - new_lock` from `locked_margin` to `free_cash`. Store `new_lock` in the order."
    *   The `leaves` in the formula must be the *new* `leaves` after the fill (i.e., `qty - new_cum_qty`).
    *   Crucial detail: `new_lock = ceil_div(new_leaves * order.price * order.margin_bps, 10000)`.
    *   `move = old_lock - new_lock`.
    *   Step:
        1. `fill_qty = min(inc.leaves, opp.leaves)`
        2. `inc.cum_qty += fill_qty`
        3. `opp.cum_qty += fill_qty`
        4. `old_inc_lock = inc.lock`
        5. `new_inc_lock = ceil_div(inc.leaves * inc.price * inc.margin_bps, 10000)`
        6. `inc.lock = new_inc_lock`
        7. `move_inc = old_inc_lock - new_inc_lock`
        8. `release_lock(state, inc.account, move_inc)`
        9. `old_opp_lock = opp.lock`
        10. `new_opp_lock = ceil_div(opp.leaves * opp.price * opp.margin_bps, 10000)`
        11. `opp.lock = new_opp_lock`
        12. `move_opp = old_opp_lock - new_opp_lock`
        13. `release_lock(state, opp.account, move_opp)`
        14. `settle_fill(...)`
        15. `if opp.leaves == 0: remove_order(state, opp.order_id)`

    *   The previous submission had:
        ```python
        # Update locks (R-M4.4 / R-M5)
        # Incoming order lock update
        old_inc_lock = incoming_order.lock
        new_inc_lock = ceil_div(incoming_order.leaves * incoming_order.price * incoming_order.margin_bps, 10000)
        # ...
        ```
    *   Wait, `incoming_order.leaves` was updated *before* this calculation.
    *   The previous code calculated:
        ```python
        incoming_order.cum_qty += fill_qty
        # ...
        rem_inc_leaves = incoming_order.leaves
        new_inc_lock = ceil_div(rem_inc_leaves * incoming_order.price * incoming_order.margin_bps, 10000)
        ```
    *   This looks mathematically correct according to the rule.
    *   Let's check the STP logic:
        ```python
        if best_opp.account == incoming_order.account:
            remove_order(state, best_opp.order_id)
            release_lock(state, best_opp.account, best_opp.lock)
            reports.append(Report.cancelled(best_opp.order_id, "STP"))
            continue
        ```
    *   Rule R-M3 says: "It moves the full lock of the resting order from `locked_margin` to `free_cash`. It reports `Report.cancelled(order_id, "STP")`."
    *   Wait, `best_opp.order_id` is the resting order ID. The rule says `Report.cancelled(order_id, "STP")`. In STP, the `order_id` in the report refers to the resting order being cancelled. Yes.

    *   One potential issue: "The reports are returned in the order in which the events happen: `ACCEPTED`, then for each step of matching the `STP` cancellation or the `FILL`, then `IOC_REMAINDER` if it applies."
    *   In the previous code:
        ```python
        reports: list[Report] = [Report.accepted(order_id)]
        while ...:
            if STP:
                reports.append(Report.cancelled(...))
            else:
                fill_reports = settle_fill(...)
                reports.extend(fill_reports)
        if IOC:
            reports.append(Report.cancelled(...))
        ```
    *   This order seems correct.

    *   Let's check R-M4 again. "For each of the two orders, compute `new_lock = ceil_div(leaves * order.price * order.margin_bps, 10000)`, using the `margin_bps` stored in that order."
    *   The `leaves` must be the *new* leaves.
    *   Wait, I see a discrepancy in the loop. If `best_opp` is fully filled, I call `remove_order`. If not, it stays in the book.
    *   The loop iterates using `opp_orders = get_asks(state)`. If I remove an order from `state.orders`, the next call to `get_asks` will reflect that.

    *   Wait, the `get_asks` and `get_bids` functions in `book.py` return a *new* list of orders.
    *   The code:
        ```python
        while incoming_order.leaves > 0:
            best_opp = None
            if incoming_order.side == "BUY":
                opp_orders = get_asks(state)
                for o in opp_orders:
                    if o.price <= incoming_order.price:
                        best_opp = o
                    else:
                        break
            else:
                opp_orders = get_bids(state)
                for o in opp_orders:
                    if o.price >= incoming_order.price:
                        best_opp = o
                    else:
                        break
        ```
    *   The logic `for o in opp_orders: if o.price <= ...: best_opp = o else: break` is actually finding the *last* order that satisfies the condition, not the *first* (best) one.
    *   `get_asks` returns orders in price-asc (best first).
    *   If `opp_orders` is `[10, 11, 12]` and `limit` is `11.5`.
    *   The loop:
        - `o=10`: `10 <= 11.5` is True. `best_opp = 10`.
        - `o=11`: `11 <= 11.5` is True. `best_opp = 11`.
        - `o=12`: `12 <= 11.5` is False. `break`.
    *   `best_opp` is `11`. But the best price is `10`!
    *   The code should take the *first* one.

    *   Corrected Matching Loop:
        ```python
        if incoming_order.side == "BUY":
            opp_orders = get_asks(state)
            for o in opp_orders:
                if o.price <= incoming_order.price:
                    best_opp = o
                    break
                else:
                    break
        ```
        Wait, even simpler:
        ```python
        if incoming_order.side == "BUY":
            opp_orders = get_asks(state)
            if opp_orders and opp_orders[0].price <= incoming_order.price:
                best_opp = opp_orders[0]
        else:
            opp_orders = get_bids(state)
            if opp_orders and opp_orders[0].price >= incoming_order.price:
                best_opp = opp_orders[0]
        ```

    *   Let's double check the lock update again.
    *   Rule R-M4.4: "Move `old_lock - new_lock` from `locked_margin` to `free_cash`."
    *   Since `new_lock` is always `<= old_lock` (as `leaves` decreases), `old_lock - new_lock` is non-negative.
    *   My code: `diff_inc = old_inc_lock - new_inc_lock`, `release_lock(state, inc.account, diff_inc)`.
    *   `release_lock` in `ledger.py`: `acc.locked_margin -= amount; acc.free_cash += amount`.
    *   This correctly moves the difference from `locked_margin` to `free_cash`.

    *   `R-B4.4`: `lock = ceil_div(qty * price * state.margin_bps, 10000)`.
    *   `R-B5.3`: Subtract `lock` from `free_cash`. Add `lock` to `locked_margin`.
    *   `R-M4.4`: `new_lock = ceil_div(leaves * order.price * order.margin_bps, 10000)`.
    *   `R-M5`: If `leaves == 0`, `new_lock = 0`.
    *   Wait, let's verify if `new_lock` calculation in R-M4.4 handles the `leaves == 0` case correctly.
    *   If `leaves == 0`, `new_lock = ceil_div(0 * price * margin, 10000) = 0`. Yes.

    *   Is there anything else?
    *   Self-trade prevention: "It removes it from the book. It moves the full lock of the resting order from `locked_margin` to `free_cash`. It reports `Report.cancelled(order_id, "STP")`. It then continues to match with the next resting order. No fill occurs for the cancelled order."
    *   My code for STP:
        ```python
        if best_opp.account == incoming_order.account:
            remove_order(state, best_opp.order_id)
            release_lock(state, best_opp.account, best_opp.lock)
            reports.append(Report.cancelled(best_opp.order_id, "STP"))
            continue
        ```
    *   This looks perfectly aligned with R-M3.

    *   The `settle_fill` call:
        ```python
        fill = Fill(
            buy_order_id=buy_id,
            sell_order_id=sell_id,
            price=fill_price,
            qty=fill_qty,
            taker_order_id=incoming_order.order_id,
            buyer=buyer_acc,
            seller=seller_acc
        )
        fill_reports = settle_fill(engine, fill)
        reports.extend(fill_reports)
        ```
    *   The rule says: "The handler builds the `Fill` for `settle_fill` with `buy_order_id` and `sell_order_id` of the two orders, the fill `price` and `qty`, `taker_order_id` equal to the incoming order, and `buyer` and `seller` equal to the accounts of the buy order and the sell order."
    *   My code:
        ```python
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
        ```
    *   This is correct.

    *   Check the return order of reports.
    *   `ACCEPTED`, then `STP`/`FILL`, then `IOC_REMAINDER`.
    *   My code:
        - `reports = [Report.accepted(order_id)]`
        - `while ...: reports.append(STP) or reports.extend(FILL)`
        - `if IOC and leaves > 0: reports.append(IOC_REMAINDER)`
    *   This matches.

    *   One more look at `new_lock` for the `incoming_order` during a fill.
    *   In R-M4.4: "For each of the two orders, compute `new_lock = ...` ... Store `new_lock` in the order."
    *   Wait, the `incoming_order` is not yet in `state.orders`. So "Store `new_lock` in the order" just means update the local `incoming_order` object. This is fine.

    *   Let's check the `margin_bps` for the `incoming_order`.
    *   R-B5.2: "Create the order with ... the current `state.margin_bps` stored in it as `margin_bps`."
    *   My code: `margin_bps=state.margin_bps`. This is correct.

    *   Final check on R-M4.4: "Move `old_lock - new_lock` from `locked_margin` to `free_cash`."
    *   If `old_lock = 100` and `new_lock = 40`, we move `60` from `locked_margin` to `free_cash`.
    *   `release_lock(state, acc, 60)` does:
        `acc.locked_margin -= 60` (100 -> 40)
        `acc.free_cash += 60`
    *   This is exactly what is required.

    *   Wait, I see one detail: `incoming_order` is local. `best_opp` is a reference to an order in `state.orders`.
    *   When `best_opp.cum_qty += fill_qty` is called, it updates the order in `state.orders`.
    *   When `remove_order(state, best_opp.order_id)` is called, it removes it from `state.orders`.
    *   If `best_opp.leaves > 0`, it stays in `state.orders`.
    *   Wait, the `get_asks` / `get_bids` return a *list* of orders. If I modify an order in that list (like `best_opp.cum_qty += fill_qty`), it *does* modify the order in `state.orders` because they are the same objects.
    *   But what if the order is fully filled?
    *   Rule R-M4: "A resting order with `leaves == 0` leaves the book."
    *   In my loop:
        ```python
        if best_opp.leaves == 0:
            remove_order(state, best_opp.order_id)
        ```
    *   This is correct.

    *   One edge case: `POST_ONLY`.
    *   R-B4.3: "If the flag is `POST_ONLY` and the order would match now, return `[Report.rejected("POST_ONLY_WOULD_CROSS")]`."
    *   "Would match now" means:
        - `BUY` crosses when `best_ask <= price`.
        - `SELL` crosses when `best_bid >= price`.
    *   My code:
        ```python
        if event.flag == "POST_ONLY":
            if event.side == "BUY":
                asks = get_asks(state)
                if asks and asks[0].price <= event.price:
                    return [Report.rejected("POST_ONLY_WOULD_CROSS")]
            else:
                bids = get_bids(state)
                if bids and bids[0].price >= event.price:
                    return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        ```
    *   Wait, `get_asks` returns the best asks. `asks[0].price` is the best ask.
    *   So if `best_ask <= price`, it would match. Correct.

    *   Check `margin_bps` usage in `new_lock` calculation:
        `new_lock = ceil_div(leaves * order.price * order.margin_bps, 10000)`
    *   Is it `order.price` or `event.price`?
    *   Rule R-M4.4: "compute `new_lock = ...` using the `margin_bps` stored in that order." It says `order.price`.
    *   For the `incoming_order`, `order.price` is `event.price`.
    *   For the `resting_order`, `order.price` is its own price.
    *   My code uses `incoming_order.price` and `best_opp.price`. Correct.

    *   Let's re-verify the `STP` return reason.
    *   Rule R-M3: "It reports `Report.cancelled(order_id, "STP")`."
    *   In STP, which `order_id`? The rule says "the handler cancels *that* resting order ... It reports `Report.cancelled(order_id, "STP")`". This implies the `order_id` is the resting order's ID.
    *   My code: `reports.append(Report.cancelled(best_opp.order_id, "STP"))`. Correct.

    *   One more check on the `incoming_order` lock update.
    *   The `incoming_order.lock` is updated in the loop.
    *   If `IOC` and `leaves > 0`, the lock is released.
    *   If `leaves == 0`, the lock should be 0.
    *   Let's trace:
        - `fill_qty = incoming_order.leaves` (incoming order is fully filled)
        - `incoming_order.cum_qty += fill_qty`
        - `rem_inc_leaves = 0`
        - `new_inc_lock = ceil_div(0 * ...) = 0`
        - `diff_inc = old_inc_lock - 0 = old_inc_lock`
        - `release_lock(state, incoming_order.account, old_inc_lock)`
        - `incoming_order.lock = 0`
    *   This is correct. Even if the order is fully filled, we must release the margin.

    *   What about the `POST_ONLY` order that isn't filled?
    *   It is added to the book. Its `lock` is already its `new_lock` because it hasn't been matched. Correct.

    *   Final thought: `best_opp` selection.
    *   My updated logic:
        ```python
        if incoming_order.side == "BUY":
            opp_orders = get_asks(state)
            if opp_orders and opp_orders[0].price <= incoming_order.price:
                best_opp = opp_orders[0]
        else:
            opp_orders = get_bids(state)
            if opp_orders and opp_orders[0].price >= incoming_order.price:
                best_opp = opp_orders[0]
        ```
    *   This is much safer.

    *   The `reports.extend(fill_reports)` might include `Report.fill(...)`.
    *   Rule R-M4.6: "Report the fill. (Done by `settle_fill`; the handler adds the returned reports to its own list.)"
    *   Yes, that's what I'm doing.

    *   Is `incoming_order.price` always the limit price? Yes.
    *   Is `best_opp.price` always the resting price? Yes.
    *   So `fill_price = best_opp.price` is correct (R-M2).

    *   One small thing: `incoming_order.margin_bps` is set to `state.margin_bps` at creation.
    *   R-B5.2: "...the current `state.margin_bps` stored in it as `margin_bps`."
    *   R-M4.4: "...using the `margin_bps` stored in that order."
    *   My code uses `incoming_order.margin_bps`. Correct.

    *   Final check on R-B5.6: "If the flag is `IOC` and `leaves > 0`, cancel the remainder with `Report.cancelled(order_id, "IOC_REMAINDER")`. Release the lock of the order: move it from `locked_margin` to `free_cash`."
    *   My code:
        ```python
        if incoming_order.leaves > 0:
            if incoming_order.flag == "IOC":
                release_lock(state, incoming_order.account, incoming_order.lock)
                reports.append(Report.cancelled(incoming_order.order_id, "IOC_REMAINDER"))
        ```
    *   This is correct.</thought>### FILE: exchange_core/handlers/new_limit.py
```python
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
```
````
