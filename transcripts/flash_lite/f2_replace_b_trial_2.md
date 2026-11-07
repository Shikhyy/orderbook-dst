# flash_lite · f2_replace_b · trial 2 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemini-3.1-flash-lite` / `gemini-3.1-flash-lite` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 8698 / 662 |
| Latency (s) | 3.536470890045166 |
| Stop reason | stop |
| Timestamp | 2026-11-04T07:29:40.432876+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/flash_lite/f2_replace_b/2/prompt.txt) (sha256 `a8d46c579386ccc9…`) |
| Raw files | [`results/main/raw/flash_lite/f2_replace_b/2/`](../../results/main/raw/flash_lite/f2_replace_b/2) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f2_replace_b/replace.py
+++ model/exchange_core/handlers/replace.py
@@ -1,111 +1,56 @@
-"""reference/f2_replace_b/replace.py
-Reference solution for task f2_replace_b.
+"""exchange_core/handlers/replace.py
+Handle REPLACE event.
+Rules R-P1 to R-P4. Target for task f2_replace_b.
 """
-from exchange_core.book import best_ask, best_bid, get_order
-from exchange_core.config import EngineConfig
+from exchange_core.types import Event, Report
+from exchange_core.book import get_order, best_ask, best_bid
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
+from exchange_core.ledger import lock_cash, release_lock
 
 
 def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process a REPLACE event according to rules R-P1 to R-P4.
-
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
+    """Process a REPLACE event according to rules R-P1 to R-P4."""
+    order = get_order(engine.state, event.order_id)
+    if order is None:
         return [Report.rejected("UNKNOWN_ORDER")]
 
-    # Rules R-P2 steps 2, 3 and R-P3: decide via replace rule
-    dec = decide_replace(order, event.new_price, event.new_qty, cfg)
-    if not dec.ok:
-        return [Report.rejected(dec.reason)]
+    if event.new_price <= 0 or event.new_price % engine.cfg.TICK != 0:
+        return [Report.rejected("INVALID_ORDER")]
 
-    # Rule R-P2 step 4: crossing check against opposite book
+    if event.new_qty <= order.cum_qty:
+        return [Report.rejected("INVALID_REPLACE")]
+
     if order.side == "BUY":
-        ask = best_ask(state)
-        if ask is not None and ask <= event.new_price:
+        ask = best_ask(engine.state)
+        if ask is not None and event.new_price >= ask:
             return [Report.rejected("REPLACE_WOULD_CROSS")]
-    elif order.side == "SELL":
-        bid = best_bid(state)
-        if bid is not None and bid >= event.new_price:
+    else:
+        bid = best_bid(engine.state)
+        if bid is not None and event.new_price <= bid:
             return [Report.rejected("REPLACE_WOULD_CROSS")]
 
-    # Rule R-P2 step 5 & R-P4: margin check using stored order.margin_bps
-    new_leaves = dec.new_leaves
-    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10_000)
-    acc = state.accounts[order.account]
+    new_leaves = event.new_qty - order.cum_qty
+    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10000)
 
-    if new_lock > order.lock:
-        diff = new_lock - order.lock
-        if acc.free_cash < diff:
-            return [Report.rejected("INSUFFICIENT_MARGIN")]
+    delta = new_lock - order.lock
+    acc = engine.state.accounts[order.account]
 
-    # Rule R-P3: priority update
-    if not dec.keep_priority:
-        order.prio_seq = state.next_prio_seq
-        state.next_prio_seq += 1
+    if delta > 0 and delta > acc.free_cash:
+        return [Report.rejected("INSUFFICIENT_MARGIN")]
 
-    # Rule R-P4: apply changes to order and ledger
-    lock_diff = new_lock - order.lock
-    acc.free_cash -= lock_diff
-    acc.locked_margin += lock_diff
+    # Update state
+    if delta > 0:
+        lock_cash(engine.state, order.account, delta)
+    elif delta < 0:
+        release_lock(engine.state, order.account, -delta)
 
+    if not (event.new_price == order.price and event.new_qty == order.qty):
+        if not (event.new_price == order.price and event.new_qty < order.qty):
+            order.prio_seq = engine.state.next_prio_seq
+            engine.state.next_prio_seq += 1
+
+    order.price = event.new_price
     order.qty = event.new_qty
-    order.price = event.new_price
     order.lock = new_lock
 
-    return [Report.replaced(order.order_id)]
+    return [Report.replaced(event.order_id)]
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
from exchange_core.book import get_order, best_ask, best_bid
from exchange_core.intmath import ceil_div
from exchange_core.ledger import lock_cash, release_lock


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    order = get_order(engine.state, event.order_id)
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    if event.new_price <= 0 or event.new_price % engine.cfg.TICK != 0:
        return [Report.rejected("INVALID_ORDER")]

    if event.new_qty <= order.cum_qty:
        return [Report.rejected("INVALID_REPLACE")]

    if order.side == "BUY":
        ask = best_ask(engine.state)
        if ask is not None and event.new_price >= ask:
            return [Report.rejected("REPLACE_WOULD_CROSS")]
    else:
        bid = best_bid(engine.state)
        if bid is not None and event.new_price <= bid:
            return [Report.rejected("REPLACE_WOULD_CROSS")]

    new_leaves = event.new_qty - order.cum_qty
    new_lock = ceil_div(new_leaves * event.new_price * order.margin_bps, 10000)

    delta = new_lock - order.lock
    acc = engine.state.accounts[order.account]

    if delta > 0 and delta > acc.free_cash:
        return [Report.rejected("INSUFFICIENT_MARGIN")]

    # Update state
    if delta > 0:
        lock_cash(engine.state, order.account, delta)
    elif delta < 0:
        release_lock(engine.state, order.account, -delta)

    if not (event.new_price == order.price and event.new_qty == order.qty):
        if not (event.new_price == order.price and event.new_qty < order.qty):
            order.prio_seq = engine.state.next_prio_seq
            engine.state.next_prio_seq += 1

    order.price = event.new_price
    order.qty = event.new_qty
    order.lock = new_lock

    return [Report.replaced(event.order_id)]
```
````
