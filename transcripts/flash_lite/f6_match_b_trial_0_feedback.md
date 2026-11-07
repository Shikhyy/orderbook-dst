# flash_lite · f6_match_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemini-3.1-flash-lite` / `None` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | feedback_loop |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 8253 / 1220 |
| Latency (s) | 14.132917165756226 |
| Stop reason | – |
| Timestamp | 2026-11-06T07:21:10.410591+00:00 |
| Prompt | [`prompt.txt`](../../results/feedback/raw/flash_lite/f6_match_b/0/prompt.txt) (sha256 `75d7ddadb330c7af…`) |
| Raw files | [`results/feedback/raw/flash_lite/f6_match_b/0/`](../../results/feedback/raw/flash_lite/f6_match_b/0) |

## Feedback-loop turns

| Turn | Score | Passed | First failure |
|---|---|---|---|
| 0 | 1.0 | True | –  |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f6_match_b/new_limit.py
+++ model/exchange_core/handlers/new_limit.py
@@ -1,53 +1,45 @@
 """exchange_core/handlers/new_limit.py
-Handle NEW_LIMIT event and execute order matching.
-Rules R-B1 to R-B5, R-M1 to R-M4. Reference only. Matching lives here.
+Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
+Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
 """
-from exchange_core.book import add_order, best_ask, best_bid, get_asks, get_bids, remove_order
 from exchange_core.handlers.settle import settle_fill
+from exchange_core.types import Event, Report, Order, Fill
+from exchange_core.state import EngineState
+from exchange_core.book import get_bids, get_asks, remove_order, add_order
 from exchange_core.intmath import ceil_div
-from exchange_core.types import Event, Fill, Order, Report
-
+from exchange_core.ledger import lock_cash, release_lock
 
 def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process a NEW_LIMIT event.
-
-    Rules R-B4, R-B5, R-M1, R-M2, R-M3, R-M4.
-    """
     state = engine.state
     cfg = engine.cfg
-    reports: list[Report] = []
 
-    # Rule R-B4 step 1: unknown account check
+    # 1. Validation
     if event.account not in state.accounts:
         return [Report.rejected("UNKNOWN_ACCOUNT")]
-
-    # Rule R-B4 step 2: invalid order checks
     if event.qty <= 0 or event.price <= 0 or event.price % cfg.tick != 0:
         return [Report.rejected("INVALID_ORDER")]
 
-    # Rule R-B4 step 3: POST_ONLY crossing check
+    # 3. Post-only validation
     if event.flag == "POST_ONLY":
-        ask, bid = best_ask(state), best_bid(state)
-        if (event.side == "BUY" and ask is not None and ask <= event.price) or (
-            event.side == "SELL" and bid is not None and bid >= event.price
-        ):
-            return [Report.rejected("POST_ONLY_WOULD_CROSS")]
+        if event.side == "BUY":
+            best = get_asks(state)
+            if best and best[0].price <= event.price:
+                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
+        else:
+            best = get_bids(state)
+            if best and best[0].price >= event.price:
+                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
 
-    # Rule R-B4 step 4: margin check
-    acc = state.accounts[event.account]
-    lock = ceil_div(event.qty * event.price * state.margin_bps, 10_000)
-    if acc.free_cash < lock:
+    # 4. Margin validation
+    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
+    if state.accounts[event.account].free_cash < lock:
         return [Report.rejected("INSUFFICIENT_MARGIN")]
 
-    # Rule R-B5 step 1: assign order_id and prio_seq from counters
+    # 5. Initialization
     order_id = state.next_order_id
+    state.next_order_id += 1
     prio_seq = state.next_prio_seq
-    state.next_order_id += 1
     state.next_prio_seq += 1
-
-    # Rule R-B5 step 2 & 3: create order, store engine margin_bps, lock margin
-    acc.free_cash -= lock
-    acc.locked_margin += lock
 
     order = Order(
         order_id=order_id,
@@ -59,91 +51,61 @@
         prio_seq=prio_seq,
         margin_bps=state.margin_bps,
         lock=lock,
-        flag=event.flag,
+        flag=event.flag
     )
 
-    # Rule R-B5 step 4: report ACCEPTED
-    reports.append(Report.accepted(order_id))
+    lock_cash(state, event.account, lock)
+    reports = [Report.accepted(order_id)]
 
-    # Rule R-B5 step 5: match the order (Rules R-M1 to R-M4)
+    # Matching
     while order.leaves > 0:
-        # Rule R-M1: find best candidate resting order
-        resting_candidates = get_asks(state) if order.side == "BUY" else get_bids(state)
-        if not resting_candidates:
+        candidates = get_asks(state) if event.side == "BUY" else get_bids(state)
+        if not candidates:
             break
-
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
+        best = candidates[0]
+        
+        # Cross logic
+        if event.side == "BUY" and best.price > event.price: break
+        if event.side == "SELL" and best.price < event.price: break
+        
+        # STP
+        if best.account == event.account:
+            remove_order(state, best.order_id)
+            release_lock(state, best.account, best.lock)
+            reports.append(Report.cancelled(best.order_id, "STP"))
             continue
-
-        # Rule R-M2: fill price is resting price; fill quantity is min(leaves)
-        fill_price = best_resting.price
-        fill_qty = min(order.leaves, best_resting.leaves)
-
-        # Rule R-M4 step 3 & 4: adjust cum_qty and locks for both orders
-        # 1. Update maker (resting order)
-        maker_old_lock = best_resting.lock
-        best_resting.cum_qty += fill_qty
-        maker_new_lock = ceil_div(
-            best_resting.leaves * best_resting.price * best_resting.margin_bps, 10_000
+            
+        # Fill
+        fill_qty = min(order.leaves, best.leaves)
+        fill = Fill(
+            buy_order_id=(order_id if event.side == "BUY" else best.order_id),
+            sell_order_id=(best.order_id if event.side == "BUY" else order_id),
+            price=best.price,
+            qty=fill_qty,
+            taker_order_id=order_id,
+            buyer=(event.account if event.side == "BUY" else best.account),
+            seller=(best.account if event.side == "BUY" else event.account)
         )
-        maker_release = maker_old_lock - maker_new_lock
-        state.accounts[best_resting.account].locked_margin -= maker_release
-        state.accounts[best_resting.account].free_cash += maker_release
-        best_resting.lock = maker_new_lock
-
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
-        fill = Fill(
-            buy_order_id=order.order_id if is_buy else best_resting.order_id,
-            sell_order_id=best_resting.order_id if is_buy else order.order_id,
-            price=fill_price,
-            qty=fill_qty,
-            taker_order_id=order.order_id,
-            buyer=order.account if is_buy else best_resting.account,
-            seller=best_resting.account if is_buy else order.account,
-        )
-
-        # Rule R-M4 steps 1, 2, 5, 6: settle fill financial effects
-        fill_reports = settle_fill(engine, fill)
-        reports.extend(fill_reports)
-
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
-
+        reports.extend(settle_fill(engine, fill))
+        
+        for o in [order, best]:
+            old_lock = o.lock
+            o.cum_qty += fill_qty
+            if o.leaves > 0:
+                o.lock = ceil_div(o.leaves * o.price * o.margin_bps, 10000)
+            else:
+                o.lock = 0
+            release_lock(state, o.account, old_lock - o.lock)
+            
+        if best.leaves == 0:
+            remove_order(state, best.order_id)
+            
+    # Finalize
+    if order.leaves > 0:
+        if event.flag == "IOC":
+            release_lock(state, order.account, order.lock)
+            reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
+        else:
+            add_order(state, order)
+    
     return reports
```

## Author analysis

_Write after reading the reply: what the model got wrong and why, or whether the grader rejected a valid answer._

## Model reply (verbatim)

````text
### FILE: exchange_core/handlers/new_limit.py
```python
"""exchange_core/handlers/new_limit.py
Handler for NEW_LIMIT events: validation, margin, matching and fill settlement.
Rules R-B4, R-B5, R-M1 to R-M5. Target for task f6_match_b.
"""
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Event, Report, Order, Fill
from exchange_core.state import EngineState
from exchange_core.book import get_bids, get_asks, remove_order, add_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import lock_cash, release_lock

def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    state = engine.state
    cfg = engine.cfg

    # 1. Validation
    if event.account not in state.accounts:
        return [Report.rejected("UNKNOWN_ACCOUNT")]
    if event.qty <= 0 or event.price <= 0 or event.price % cfg.tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # 3. Post-only validation
    if event.flag == "POST_ONLY":
        if event.side == "BUY":
            best = get_asks(state)
            if best and best[0].price <= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]
        else:
            best = get_bids(state)
            if best and best[0].price >= event.price:
                return [Report.rejected("POST_ONLY_WOULD_CROSS")]

    # 4. Margin validation
    lock = ceil_div(event.qty * event.price * state.margin_bps, 10000)
    if state.accounts[event.account].free_cash < lock:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # 5. Initialization
    order_id = state.next_order_id
    state.next_order_id += 1
    prio_seq = state.next_prio_seq
    state.next_prio_seq += 1

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
        flag=event.flag
    )

    lock_cash(state, event.account, lock)
    reports = [Report.accepted(order_id)]

    # Matching
    while order.leaves > 0:
        candidates = get_asks(state) if event.side == "BUY" else get_bids(state)
        if not candidates:
            break
        best = candidates[0]
        
        # Cross logic
        if event.side == "BUY" and best.price > event.price: break
        if event.side == "SELL" and best.price < event.price: break
        
        # STP
        if best.account == event.account:
            remove_order(state, best.order_id)
            release_lock(state, best.account, best.lock)
            reports.append(Report.cancelled(best.order_id, "STP"))
            continue
            
        # Fill
        fill_qty = min(order.leaves, best.leaves)
        fill = Fill(
            buy_order_id=(order_id if event.side == "BUY" else best.order_id),
            sell_order_id=(best.order_id if event.side == "BUY" else order_id),
            price=best.price,
            qty=fill_qty,
            taker_order_id=order_id,
            buyer=(event.account if event.side == "BUY" else best.account),
            seller=(best.account if event.side == "BUY" else event.account)
        )
        reports.extend(settle_fill(engine, fill))
        
        for o in [order, best]:
            old_lock = o.lock
            o.cum_qty += fill_qty
            if o.leaves > 0:
                o.lock = ceil_div(o.leaves * o.price * o.margin_bps, 10000)
            else:
                o.lock = 0
            release_lock(state, o.account, old_lock - o.lock)
            
        if best.leaves == 0:
            remove_order(state, best.order_id)
            
    # Finalize
    if order.leaves > 0:
        if event.flag == "IOC":
            release_lock(state, order.account, order.lock)
            reports.append(Report.cancelled(order_id, "IOC_REMAINDER"))
        else:
            add_order(state, order)
    
    return reports
```
````
