# flash_lite · f4_waterfall_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemini-3.1-flash-lite` / `None` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | feedback_loop |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 9262 / 774 |
| Latency (s) | 2.7106990814208984 |
| Stop reason | – |
| Timestamp | 2026-11-06T07:18:22.954676+00:00 |
| Prompt | [`prompt.txt`](../../results/feedback/raw/flash_lite/f4_waterfall_b/0/prompt.txt) (sha256 `efc0519d18c2ffce…`) |
| Raw files | [`results/feedback/raw/flash_lite/f4_waterfall_b/0/`](../../results/feedback/raw/flash_lite/f4_waterfall_b/0) |

## Feedback-loop turns

| Turn | Score | Passed | First failure |
|---|---|---|---|
| 0 | 1.0 | True | –  |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f4_waterfall_b/shock.py
+++ model/exchange_core/handlers/shock.py
@@ -1,80 +1,59 @@
 """exchange_core/handlers/shock.py
-Handle PRICE_SHOCK event and margin waterfall liquidation.
+Handler for PRICE_SHOCK and liquidation waterfall.
 Rules R-W1 to R-W6. Target for task f4_waterfall_b.
 """
+from exchange_core.types import Event, Report
 from exchange_core.book import get_account_orders, remove_order
 from exchange_core.intmath import ceil_div
-from exchange_core.types import Event, Report
+from exchange_core.ledger import release_lock, transfer_cash, adjust_position
 
 
 def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process PRICE_SHOCK event and run margin waterfall.
+    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
+    engine.state.mark_price = event.mark_price
+    reports = [Report.mark_set(mark_price=event.mark_price)]
+    maint_bps = engine.cfg.MAINT_BPS
 
-    Rules R-W1 to R-W6:
-    1. Set mark_price. Emit MARK_SET.
-    2. Iterate over accounts (except LIQ) in ascending order.
-    3. Stage 1: if breach, cancel resting orders in ascending prio_seq order.
-    4. Stage 2: if still in breach, liquidate position against LIQ.
-    """
-    state = engine.state
-    cfg = engine.cfg
-    reports: list[Report] = []
+    def is_in_breach(account_id: str) -> bool:
+        acc = engine.state.accounts[account_id]
+        if acc.position == 0:
+            return False
+        avail = acc.free_cash + (acc.position * engine.state.mark_price)
+        req = ceil_div(abs(acc.position) * engine.state.mark_price * maint_bps, 10000)
+        return avail < req
 
-    # Rule R-W1: set mark_price
-    state.mark_price = event.mark_price
-    reports.append(Report.mark_set(event.mark_price))
+    account_ids = sorted([acc_id for acc_id in engine.state.accounts if acc_id != "LIQ"])
 
-    # Rule R-W1: iterate accounts except LIQ in ascending account-id order
-    sorted_accounts = sorted([a for a in state.accounts if a != "LIQ"])
-
-    for acc_id in sorted_accounts:
-        acc = state.accounts[acc_id]
-
-        # Rule R-W2: position == 0 is never in breach
-        if acc.position == 0:
-            continue
-
-        # Breach calculation
-        avail = acc.free_cash + acc.position * state.mark_price
-        req = ceil_div(abs(acc.position) * state.mark_price * cfg.maint_bps, 10_000)
-
-        if avail >= req:
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
-        reports.append(Report.liquidated(acc_id, orig_position))
+    for acc_id in account_ids:
+        # Stage 1: Cancel orders if in breach
+        if is_in_breach(acc_id):
+            orders = get_account_orders(engine.state, acc_id)
+            for o in orders:
+                remove_order(engine.state, o.order_id)
+                release_lock(engine.state, acc_id, o.lock)
+                reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))
+                # Re-check breach after each cancellation? Rule R-W4 implies re-computing after Stage 1,
+                # but Rule R-W3 implies canceling in order while in breach.
+                # Following typical waterfall: cancel all to see if breach resolves.
+        
+        # Stage 2: Liquidate if still in breach
+        if is_in_breach(acc_id):
+            acc = engine.state.accounts[acc_id]
+            orig_pos = acc.position
+            
+            # Liquidation transfer
+            amount = abs(orig_pos) * engine.state.mark_price
+            if orig_pos > 0:
+                # Account sells: transfer cash from LIQ to account
+                transfer_cash(engine.state, "LIQ", acc_id, amount)
+            else:
+                # Account buys: transfer cash from account to LIQ
+                transfer_cash(engine.state, acc_id, "LIQ", amount)
+            
+            # Update positions
+            adjust_position(engine.state, acc_id, -orig_pos)
+            adjust_position(engine.state, "LIQ", orig_pos)
+            
+            reports.append(Report.liquidated(account=acc_id, qty=orig_pos))
 
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
from exchange_core.types import Event, Report
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock, transfer_cash, adjust_position


def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    engine.state.mark_price = event.mark_price
    reports = [Report.mark_set(mark_price=event.mark_price)]
    maint_bps = engine.cfg.MAINT_BPS

    def is_in_breach(account_id: str) -> bool:
        acc = engine.state.accounts[account_id]
        if acc.position == 0:
            return False
        avail = acc.free_cash + (acc.position * engine.state.mark_price)
        req = ceil_div(abs(acc.position) * engine.state.mark_price * maint_bps, 10000)
        return avail < req

    account_ids = sorted([acc_id for acc_id in engine.state.accounts if acc_id != "LIQ"])

    for acc_id in account_ids:
        # Stage 1: Cancel orders if in breach
        if is_in_breach(acc_id):
            orders = get_account_orders(engine.state, acc_id)
            for o in orders:
                remove_order(engine.state, o.order_id)
                release_lock(engine.state, acc_id, o.lock)
                reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))
                # Re-check breach after each cancellation? Rule R-W4 implies re-computing after Stage 1,
                # but Rule R-W3 implies canceling in order while in breach.
                # Following typical waterfall: cancel all to see if breach resolves.
        
        # Stage 2: Liquidate if still in breach
        if is_in_breach(acc_id):
            acc = engine.state.accounts[acc_id]
            orig_pos = acc.position
            
            # Liquidation transfer
            amount = abs(orig_pos) * engine.state.mark_price
            if orig_pos > 0:
                # Account sells: transfer cash from LIQ to account
                transfer_cash(engine.state, "LIQ", acc_id, amount)
            else:
                # Account buys: transfer cash from account to LIQ
                transfer_cash(engine.state, acc_id, "LIQ", amount)
            
            # Update positions
            adjust_position(engine.state, acc_id, -orig_pos)
            adjust_position(engine.state, "LIQ", orig_pos)
            
            reports.append(Report.liquidated(account=acc_id, qty=orig_pos))

    return reports
```
````
