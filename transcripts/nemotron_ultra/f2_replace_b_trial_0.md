# nemotron_ultra · f2_replace_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `nvidia/nemotron-3-ultra-550b-a55b:free` / `nvidia/nemotron-3-ultra-550b-a55b:free` |
| Settings | `{"max_tokens": 16000, "base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 7846 / 4177 |
| Latency (s) | 63.473406076431274 |
| Stop reason | stop |
| Timestamp | 2026-11-04T06:02:15.570573+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/nemotron_ultra/f2_replace_b/0/prompt.txt) (sha256 `a8d46c579386ccc9…`) |
| Raw files | [`results/main/raw/nemotron_ultra/f2_replace_b/0/`](../../results/main/raw/nemotron_ultra/f2_replace_b/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f2_replace_b/replace.py
+++ model/exchange_core/handlers/replace.py
@@ -1,111 +1,82 @@
-"""reference/f2_replace_b/replace.py
-Reference solution for task f2_replace_b.
+"""exchange_core/handlers/replace.py
+Handle REPLACE event.
+Rules R-P1 to R-P4. Target for task f2_replace_b.
 """
-from exchange_core.book import best_ask, best_bid, get_order
-from exchange_core.config import EngineConfig
+from exchange_core.types import Event, Report
 from exchange_core.intmath import ceil_div
-from exchange_core.types import Event, Order, ReplaceDecision, Report
-
-# --- Rule logic (replace_rule), written out here because Variant B code may not
-# import exchange_core.rules.* (see the task's 'Allowed imports'). ---
-
-def decide_replace(
-    order: Order,
-    new_price: int,
-    new_qty: int,
-    cfg: EngineConfig,
-) -> ReplaceDecision:
-    """Decide whether a replace request is valid and whether it keeps priority.
-
-    Rules R-P1, R-P2 (steps 2 and 3), R-P3:
-    - Step 2: If new_price <= 0 or new_price % TICK != 0: REJECTED(INVALID_ORDER)
-    - Step 3: If new_qty <= cum_qty: REJECTED(INVALID_REPLACE)
-    - Priority:
-      - If new_price == old_price and new_qty < old_qty: keeps prio_seq
-      - If new_price == old_price and new_qty == old_qty: nothing changes (keeps prio_seq)
-      - In all other cases (price change or qty increase): gets new prio_seq
-    """
-    # Rule R-P2 step 2: price validation
-    if new_price <= 0 or new_price % cfg.tick != 0:
-        return ReplaceDecision(ok=False, reason="INVALID_ORDER", keep_priority=False, new_leaves=0)
-
-    # Rule R-P2 step 3: quantity vs cum_qty
-    if new_qty <= order.cum_qty:
-        return ReplaceDecision(
-            ok=False, reason="INVALID_REPLACE", keep_priority=False, new_leaves=0
-        )
-
-    new_leaves = new_qty - order.cum_qty
-
-    # Rule R-P3: priority determination
-    if new_price == order.price and new_qty <= order.qty:
-        keep_priority = True
-    else:
-        keep_priority = False
-
-    return ReplaceDecision(
-        ok=True,
-        reason="",
-        keep_priority=keep_priority,
-        new_leaves=new_leaves,
-    )
+from exchange_core.book import best_bid, best_ask
+from exchange_core.ledger import get_account, lock_cash, release_lock
 
 
 def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process a REPLACE event according to rules R-P1 to R-P4.
+    """Process a REPLACE event according to rules R-P1 to R-P4."""
+    order_id = event.order_id
+    new_price = event.new_price
+    new_qty = event.new_qty
 
-    Rejection order (Rule R-P2):
-    1. Not resting: UNKNOWN_ORDER
-    2. new_price <= 0 or new_price % TICK != 0: INVALID_ORDER
-    3. new_qty <= cum_qty: INVALID_REPLACE
-    4. New price would match opposite book: REPLACE_WOULD_CROSS
-    5. Insufficient margin for lock increase: INSUFFICIENT_MARGIN
-    """
-    state = engine.state
-    cfg = engine.cfg
-
-    # Rule R-P2 step 1: check order is resting
-    order = get_order(state, event.order_id)
-    if order is None or order.leaves <= 0:
+    # R-P2.1: Check if order is resting
+    order = engine.state.orders.get(order_id)
+    if order is None:
         return [Report.rejected("UNKNOWN_ORDER")]
 
-    # Rules R-P2 steps 2, 3 and R-P3: decide via replace rule
-    dec = decide_replace(order, event.new_price, event.new_qty, cfg)
-    if not dec.ok:
-        return [Report.rejected(dec.reason)]
+    # R-P2.2: Check price validity
+    tick = engine.cfg.TICK
+    if new_price <= 0 or new_price % tick != 0:
+        return [Report.rejected("INVALID_ORDER")]
 
-    # Rule R-P2 step 4: crossing check against opposite book
+    # R-P2.3: Check new_qty > cum_qty
+    if new_qty <= order.cum_qty:
+        return [Report.rejected("INVALID_REPLACE")]
+
+    # R-P2.4: Check if new price would cross the book
     if order.side == "BUY":
-        ask = best_ask(state)
-        if ask is not None and ask <= event.new_price:
+        current_best_ask = best_ask(engine.state)
+        if current_best_ask is not None and new_price >= current_best_ask:
             return [Report.rejected("REPLACE_WOULD_CROSS")]
-    elif order.side == "SELL":
-        bid = best_bid(state)
-        if bid is not None and bid >= event.new_price:
+    else:  # SELL
+        current_best_bid = best_bid(engine.state)
+        if current_best_bid is not None and new_price <= current_best_bid:
             return [Report.rejected("REPLACE_WOULD_CROSS")]
 
-    # Rule R-P2 step 5 & R-P4: margin check using stored order.margin_bps
-    new_leaves = dec.new_leaves
-    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10_000)
-    acc = state.accounts[order.account]
+    # Calculate new lock using order's stored margin_bps
+    new_leaves = new_qty - order.cum_qty
+    new_lock = ceil_div(new_leaves * new_price * order.margin_bps, 10000)
 
+    # R-P2.5: Check margin sufficiency
     if new_lock > order.lock:
-        diff = new_lock - order.lock
-        if acc.free_cash < diff:
+        additional_lock = new_lock - order.lock
+        account = get_account(engine.state, order.account)
+        if account is None or additional_lock > account.free_cash:
             return [Report.rejected("INSUFFICIENT_MARGIN")]
 
-    # Rule R-P3: priority update
-    if not dec.keep_priority:
-        order.prio_seq = state.next_prio_seq
-        state.next_prio_seq += 1
+    # All checks passed - perform the replacement
+    old_lock = order.lock
+    old_price = order.price
+    old_qty = order.qty
 
-    # Rule R-P4: apply changes to order and ledger
-    lock_diff = new_lock - order.lock
-    acc.free_cash -= lock_diff
-    acc.locked_margin += lock_diff
-
-    order.qty = event.new_qty
-    order.price = event.new_price
+    # Update order fields
+    order.qty = new_qty
+    order.price = new_price
     order.lock = new_lock
 
-    return [Report.replaced(order.order_id)]
+    # Adjust account margin
+    if new_lock > old_lock:
+        lock_cash(engine.state, order.account, new_lock - old_lock)
+    elif new_lock < old_lock:
+        release_lock(engine.state, order.account, old_lock - new_lock)
+
+    # R-P3: Handle priority
+    keep_priority = False
+    if new_price == old_price:
+        if new_qty <= old_qty:
+            keep_priority = True
+        else:  # new_qty > old_qty
+            keep_priority = False
+    else:  # price change
+        keep_priority = False
+
+    if not keep_priority:
+        order.prio_seq = engine.state.next_prio_seq
+        engine.state.next_prio_seq += 1
+
+    return [Report.replaced(order_id)]
```

## Author analysis

_Write after reading the reply: what the model got wrong and why, or whether the grader rejected a valid answer._

## Model reply (verbatim)

````text
### FILE: exchange_core/handlers/replace.py
```python
"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.types import Event, Report
from exchange_core.intmath import ceil_div
from exchange_core.book import best_bid, best_ask
from exchange_core.ledger import get_account, lock_cash, release_lock


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    order_id = event.order_id
    new_price = event.new_price
    new_qty = event.new_qty

    # R-P2.1: Check if order is resting
    order = engine.state.orders.get(order_id)
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    # R-P2.2: Check price validity
    tick = engine.cfg.TICK
    if new_price <= 0 or new_price % tick != 0:
        return [Report.rejected("INVALID_ORDER")]

    # R-P2.3: Check new_qty > cum_qty
    if new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    # R-P2.4: Check if new price would cross the book
    if order.side == "BUY":
        current_best_ask = best_ask(engine.state)
        if current_best_ask is not None and new_price >= current_best_ask:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    else:  # SELL
        current_best_bid = best_bid(engine.state)
        if current_best_bid is not None and new_price <= current_best_bid:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    # Calculate new lock using order's stored margin_bps
    new_leaves = new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * new_price * order.margin_bps, 10000)

    # R-P2.5: Check margin sufficiency
    if new_lock > order.lock:
        additional_lock = new_lock - order.lock
        account = get_account(engine.state, order.account)
        if account is None or additional_lock > account.free_cash:
            return [Report.rejected("INSUFFICIENT_MARGIN")]

    # All checks passed - perform the replacement
    old_lock = order.lock
    old_price = order.price
    old_qty = order.qty

    # Update order fields
    order.qty = new_qty
    order.price = new_price
    order.lock = new_lock

    # Adjust account margin
    if new_lock > old_lock:
        lock_cash(engine.state, order.account, new_lock - old_lock)
    elif new_lock < old_lock:
        release_lock(engine.state, order.account, old_lock - new_lock)

    # R-P3: Handle priority
    keep_priority = False
    if new_price == old_price:
        if new_qty <= old_qty:
            keep_priority = True
        else:  # new_qty > old_qty
            keep_priority = False
    else:  # price change
        keep_priority = False

    if not keep_priority:
        order.prio_seq = engine.state.next_prio_seq
        engine.state.next_prio_seq += 1

    return [Report.replaced(order_id)]
```
````
