# flash_lite · f4_waterfall_b · trial 2 — failure (lowest score)

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemini-3.1-flash-lite` / `gemini-3.1-flash-lite` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 0.2958 (0.6666666666666666 / 0.125 / 0.25) |
| Outcome | D1 |
| Error | – |
| Tokens in / out | 9262 / 784 |
| Latency (s) | 2.7250912189483643 |
| Stop reason | stop |
| Timestamp | 2026-11-04T07:31:51.678543+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/flash_lite/f4_waterfall_b/2/prompt.txt) (sha256 `efc0519d18c2ffce…`) |
| Raw files | [`results/main/raw/flash_lite/f4_waterfall_b/2/`](../../results/main/raw/flash_lite/f4_waterfall_b/2) |

## First failure (hidden trace)

- Seed 7000, event 200: **D1** — Final account state mismatch
- Message: `account LIQ final balance differs`

```json
{}
```

## Labels on all failing hidden seeds

D1×7, D1_FINAL×8 (over 15 failing seeds of 20)

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f4_waterfall_b/shock.py
+++ model/exchange_core/handlers/shock.py
@@ -1,80 +1,60 @@
 """exchange_core/handlers/shock.py
-Handle PRICE_SHOCK event and margin waterfall liquidation.
+Handler for PRICE_SHOCK and liquidation waterfall.
 Rules R-W1 to R-W6. Target for task f4_waterfall_b.
 """
+from typing import Any
 from exchange_core.book import get_account_orders, remove_order
 from exchange_core.intmath import ceil_div
+from exchange_core.ledger import release_lock, transfer_cash, adjust_position
 from exchange_core.types import Event, Report
 
 
-def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process PRICE_SHOCK event and run margin waterfall.
+def is_in_breach(account_id: str, state: Any, mark_price: int, maint_bps: int) -> bool:
+    """R-W2: Check if an account is in breach."""
+    acc = state.accounts[account_id]
+    if acc.position == 0:
+        return False
+    avail = acc.free_cash + (acc.position * mark_price)
+    req = ceil_div(abs(acc.position) * mark_price * maint_bps, 10000)
+    return avail < req
 
-    Rules R-W1 to R-W6:
-    1. Set mark_price. Emit MARK_SET.
-    2. Iterate over accounts (except LIQ) in ascending order.
-    3. Stage 1: if breach, cancel resting orders in ascending prio_seq order.
-    4. Stage 2: if still in breach, liquidate position against LIQ.
-    """
-    state = engine.state
-    cfg = engine.cfg
-    reports: list[Report] = []
 
-    # Rule R-W1: set mark_price
-    state.mark_price = event.mark_price
-    reports.append(Report.mark_set(event.mark_price))
+def handle_shock(engine: Any, event: Event) -> list[Report]:
+    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
+    reports = [Report.mark_set(mark_price=event.mark_price)]
+    engine.state.mark_price = event.mark_price
+    maint_bps = engine.cfg.MAINT_BPS
 
-    # Rule R-W1: iterate accounts except LIQ in ascending account-id order
-    sorted_accounts = sorted([a for a in state.accounts if a != "LIQ"])
+    # Filter out LIQ and sort accounts by ID
+    account_ids = sorted([acc for acc in engine.state.accounts if acc != "LIQ"])
 
-    for acc_id in sorted_accounts:
-        acc = state.accounts[acc_id]
+    for acc_id in account_ids:
+        # Stage 1: Cancel orders if in breach
+        if is_in_breach(acc_id, engine.state, engine.state.mark_price, maint_bps):
+            orders = get_account_orders(engine.state, acc_id)
+            for o in orders:
+                release_lock(engine.state, acc_id, o.lock)
+                remove_order(engine.state, o.order_id)
+                reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))
+                
+                # Check breach again after each cancel (R-W4)
+                if not is_in_breach(acc_id, engine.state, engine.state.mark_price, maint_bps):
+                    break
 
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
+        # Stage 2: Liquidate if still in breach (R-W5)
+        if is_in_breach(acc_id, engine.state, engine.state.mark_price, maint_bps):
+            pos = engine.state.accounts[acc_id].position
+            notional = abs(pos * engine.state.mark_price)
+            
+            if pos > 0:
+                # Sell to LIQ
+                transfer_cash(engine.state, "LIQ", acc_id, notional)
+            else:
+                # Buy from LIQ
+                transfer_cash(engine.state, acc_id, "LIQ", notional)
+            
+            adjust_position(engine.state, "LIQ", -pos)
+            adjust_position(engine.state, acc_id, -pos)
+            reports.append(Report.liquidated(account=acc_id, qty=pos))
 
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
from typing import Any
from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import release_lock, transfer_cash, adjust_position
from exchange_core.types import Event, Report


def is_in_breach(account_id: str, state: Any, mark_price: int, maint_bps: int) -> bool:
    """R-W2: Check if an account is in breach."""
    acc = state.accounts[account_id]
    if acc.position == 0:
        return False
    avail = acc.free_cash + (acc.position * mark_price)
    req = ceil_div(abs(acc.position) * mark_price * maint_bps, 10000)
    return avail < req


def handle_shock(engine: Any, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
    reports = [Report.mark_set(mark_price=event.mark_price)]
    engine.state.mark_price = event.mark_price
    maint_bps = engine.cfg.MAINT_BPS

    # Filter out LIQ and sort accounts by ID
    account_ids = sorted([acc for acc in engine.state.accounts if acc != "LIQ"])

    for acc_id in account_ids:
        # Stage 1: Cancel orders if in breach
        if is_in_breach(acc_id, engine.state, engine.state.mark_price, maint_bps):
            orders = get_account_orders(engine.state, acc_id)
            for o in orders:
                release_lock(engine.state, acc_id, o.lock)
                remove_order(engine.state, o.order_id)
                reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))
                
                # Check breach again after each cancel (R-W4)
                if not is_in_breach(acc_id, engine.state, engine.state.mark_price, maint_bps):
                    break

        # Stage 2: Liquidate if still in breach (R-W5)
        if is_in_breach(acc_id, engine.state, engine.state.mark_price, maint_bps):
            pos = engine.state.accounts[acc_id].position
            notional = abs(pos * engine.state.mark_price)
            
            if pos > 0:
                # Sell to LIQ
                transfer_cash(engine.state, "LIQ", acc_id, notional)
            else:
                # Buy from LIQ
                transfer_cash(engine.state, acc_id, "LIQ", notional)
            
            adjust_position(engine.state, "LIQ", -pos)
            adjust_position(engine.state, acc_id, -pos)
            reports.append(Report.liquidated(account=acc_id, qty=pos))

    return reports
```
````
