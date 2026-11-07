# nemotron_ultra · f4_waterfall_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `nvidia/nemotron-3-ultra-550b-a55b:free` / `nvidia/nemotron-3-ultra-550b-a55b:free` |
| Settings | `{"max_tokens": 16000, "base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 8427 / 1254 |
| Latency (s) | 20.832781076431274 |
| Stop reason | stop |
| Timestamp | 2026-11-04T06:04:22.041698+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/nemotron_ultra/f4_waterfall_b/0/prompt.txt) (sha256 `efc0519d18c2ffce…`) |
| Raw files | [`results/main/raw/nemotron_ultra/f4_waterfall_b/0/`](../../results/main/raw/nemotron_ultra/f4_waterfall_b/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f4_waterfall_b/shock.py
+++ model/exchange_core/handlers/shock.py
@@ -1,80 +1,73 @@
 """exchange_core/handlers/shock.py
-Handle PRICE_SHOCK event and margin waterfall liquidation.
+Handler for PRICE_SHOCK and liquidation waterfall.
 Rules R-W1 to R-W6. Target for task f4_waterfall_b.
 """
 from exchange_core.book import get_account_orders, remove_order
 from exchange_core.intmath import ceil_div
+from exchange_core.ledger import release_lock, transfer_cash, adjust_position
 from exchange_core.types import Event, Report
 
 
 def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process PRICE_SHOCK event and run margin waterfall.
-
-    Rules R-W1 to R-W6:
-    1. Set mark_price. Emit MARK_SET.
-    2. Iterate over accounts (except LIQ) in ascending order.
-    3. Stage 1: if breach, cancel resting orders in ascending prio_seq order.
-    4. Stage 2: if still in breach, liquidate position against LIQ.
-    """
-    state = engine.state
-    cfg = engine.cfg
+    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
     reports: list[Report] = []
-
-    # Rule R-W1: set mark_price
-    state.mark_price = event.mark_price
+    
+    # R-W1: Set mark_price and emit MARK_SET
+    engine.state.mark_price = event.mark_price
     reports.append(Report.mark_set(event.mark_price))
-
-    # Rule R-W1: iterate accounts except LIQ in ascending account-id order
-    sorted_accounts = sorted([a for a in state.accounts if a != "LIQ"])
-
-    for acc_id in sorted_accounts:
-        acc = state.accounts[acc_id]
-
-        # Rule R-W2: position == 0 is never in breach
-        if acc.position == 0:
+    
+    # Get MAINT_BPS from config
+    maint_bps = engine.cfg.MAINT_BPS
+    mark_price = engine.state.mark_price
+    
+    # Process accounts in ascending account-id order, excluding LIQ
+    for acc_id in sorted(engine.state.accounts.keys()):
+        if acc_id == "LIQ":
             continue
-
-        # Breach calculation
-        avail = acc.free_cash + acc.position * state.mark_price
-        req = ceil_div(abs(acc.position) * state.mark_price * cfg.maint_bps, 10_000)
-
+            
+        account = engine.state.accounts[acc_id]
+        position = account.position
+        
+        # R-W2: Account with position == 0 is never in breach
+        if position == 0:
+            continue
+        
+        # Check breach: avail = free_cash + position * mark_price
+        # req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)
+        avail = account.free_cash + position * mark_price
+        req = ceil_div(abs(position) * mark_price * maint_bps, 10000)
+        
         if avail >= req:
-            continue
-
-        # Rule R-W3: Stage 1 cancel resting orders in ascending prio_seq order
-        orders = get_account_orders(state, acc_id)
-        for o in orders:
-            remove_order(state, o.order_id)
-            acc.locked_margin -= o.lock
-            acc.free_cash += o.lock
-            o.lock = 0
-            reports.append(Report.cancelled(o.order_id, "RISK"))
-
-        # Rule R-W4: re-evaluate breach test with new free_cash
-        new_avail = acc.free_cash + acc.position * state.mark_price
-        if new_avail >= req:
-            # Breach resolved by stage 1
-            continue
-
-        # Rule R-W5: Stage 2 liquidate whole position at mark_price against LIQ
-        orig_position = acc.position
-        liq_account = state.accounts["LIQ"]
-
-        if orig_position > 0:
-            # Account sells position to LIQ
-            transfer_amount = orig_position * state.mark_price
-            acc.free_cash += transfer_amount
-            liq_account.free_cash -= transfer_amount
-            acc.position = 0
-            liq_account.position += orig_position
-        else:
-            # Account buys abs(position) from LIQ
-            transfer_amount = abs(orig_position) * state.mark_price
-            acc.free_cash -= transfer_amount
-            liq_account.free_cash += transfer_amount
-            acc.position = 0
-            liq_account.position += orig_position  # orig_position is negative
-
+            continue  # Not in breach
+        
+        # R-W3: Stage 1 - cancel all resting orders in ascending prio_seq order
+        orders = get_account_orders(engine.state, acc_id)
+        for order in orders:
+            # Release lock to free_cash
+            release_lock(engine.state, acc_id, order.lock)
+            # Remove order from book
+            remove_order(engine.state, order.order_id)
+            # Report cancelled
+            reports.append(Report.cancelled(order.order_id, "RISK"))
+        
+        # R-W4: Recompute breach after stage 1
+        avail = account.free_cash + position * mark_price
+        if avail >= req:
+            continue  # Breach resolved, no liquidation
+        
+        # R-W5: Stage 2 - liquidate whole position against LIQ
+        orig_position = position
+        notional = orig_position * mark_price  # signed notional
+        
+        # Account receives notional (if long, positive; if short, negative)
+        # LIQ pays/receives opposite
+        transfer_cash(engine.state, "LIQ", acc_id, notional)
+        
+        # Adjust positions
+        adjust_position(engine.state, acc_id, -orig_position)  # Account position becomes 0
+        adjust_position(engine.state, "LIQ", orig_position)    # LIQ takes opposite position
+        
+        # Report liquidation with signed qty (original position)
         reports.append(Report.liquidated(acc_id, orig_position))
-
+    
     return reports
```

## Author analysis

_Write after reading the reply: what the model got wrong and why, or whether the grader rejected a valid answer._

## Model reply (verbatim)

````text
### FILE: exchange_core/handlers/shock.py
```python
"""exchange_core/handlers/shock.py
Handler for PRICE_SHOCK and liquidation waterfall.
Rules R-W1 to R-W6. Target for task f4_waterfall_b.
"""
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock, transfer_cash, adjust_position
from exchange_core.types import Event, Report


def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    reports: list[Report] = []
    
    # R-W1: Set mark_price and emit MARK_SET
    engine.state.mark_price = event.mark_price
    reports.append(Report.mark_set(event.mark_price))
    
    # Get MAINT_BPS from config
    maint_bps = engine.cfg.MAINT_BPS
    mark_price = engine.state.mark_price
    
    # Process accounts in ascending account-id order, excluding LIQ
    for acc_id in sorted(engine.state.accounts.keys()):
        if acc_id == "LIQ":
            continue
            
        account = engine.state.accounts[acc_id]
        position = account.position
        
        # R-W2: Account with position == 0 is never in breach
        if position == 0:
            continue
        
        # Check breach: avail = free_cash + position * mark_price
        # req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)
        avail = account.free_cash + position * mark_price
        req = ceil_div(abs(position) * mark_price * maint_bps, 10000)
        
        if avail >= req:
            continue  # Not in breach
        
        # R-W3: Stage 1 - cancel all resting orders in ascending prio_seq order
        orders = get_account_orders(engine.state, acc_id)
        for order in orders:
            # Release lock to free_cash
            release_lock(engine.state, acc_id, order.lock)
            # Remove order from book
            remove_order(engine.state, order.order_id)
            # Report cancelled
            reports.append(Report.cancelled(order.order_id, "RISK"))
        
        # R-W4: Recompute breach after stage 1
        avail = account.free_cash + position * mark_price
        if avail >= req:
            continue  # Breach resolved, no liquidation
        
        # R-W5: Stage 2 - liquidate whole position against LIQ
        orig_position = position
        notional = orig_position * mark_price  # signed notional
        
        # Account receives notional (if long, positive; if short, negative)
        # LIQ pays/receives opposite
        transfer_cash(engine.state, "LIQ", acc_id, notional)
        
        # Adjust positions
        adjust_position(engine.state, acc_id, -orig_position)  # Account position becomes 0
        adjust_position(engine.state, "LIQ", orig_position)    # LIQ takes opposite position
        
        # Report liquidation with signed qty (original position)
        reports.append(Report.liquidated(acc_id, orig_position))
    
    return reports
```
````
