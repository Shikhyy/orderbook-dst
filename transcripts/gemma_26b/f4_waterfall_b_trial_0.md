# gemma_26b · f4_waterfall_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemma-4-26b-a4b-it` / `gemma-4-26b-a4b-it` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 9262 / 1130 |
| Latency (s) | 25.49890685081482 |
| Stop reason | stop |
| Timestamp | 2026-11-04T07:21:37.616193+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/gemma_26b/f4_waterfall_b/0/prompt.txt) (sha256 `efc0519d18c2ffce…`) |
| Raw files | [`results/main/raw/gemma_26b/f4_waterfall_b/0/`](../../results/main/raw/gemma_26b/f4_waterfall_b/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f4_waterfall_b/shock.py
+++ model/exchange_core/handlers/shock.py
@@ -1,80 +1,88 @@
 """exchange_core/handlers/shock.py
-Handle PRICE_SHOCK event and margin waterfall liquidation.
+Handler for PRICE_SHOCK and liquidation waterfall.
 Rules R-W1 to R-W6. Target for task f4_waterfall_b.
 """
+from typing import Any
+from exchange_core.types import Event, Report
 from exchange_core.book import get_account_orders, remove_order
 from exchange_core.intmath import ceil_div
-from exchange_core.types import Event, Report
+from exchange_core.ledger import release_lock, adjust_position, transfer_cash
 
 
-def handle_shock(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process PRICE_SHOCK event and run margin waterfall.
+def handle_shock(engine: Any, event: Event) -> list[Report]:  # type: ignore # noqa: F821
+    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
+    # R-W1: Set mark price
+    engine.state.mark_price = event.mark_price
+    reports: list[Report] = [Report.mark_set(mark_price=event.mark_price)]
 
-    Rules R-W1 to R-W6:
-    1. Set mark_price. Emit MARK_SET.
-    2. Iterate over accounts (except LIQ) in ascending order.
-    3. Stage 1: if breach, cancel resting orders in ascending prio_seq order.
-    4. Stage 2: if still in breach, liquidate position against LIQ.
-    """
-    state = engine.state
-    cfg = engine.cfg
-    reports: list[Report] = []
+    # R-W1: Get accounts except LIQ, sorted by ID ascending
+    account_ids = sorted([acc_id for acc_id in engine.state.accounts if acc_id != "LIQ"])
 
-    # Rule R-W1: set mark_price
-    state.mark_price = event.mark_price
-    reports.append(Report.mark_set(event.mark_price))
+    for acc_id in account_ids:
+        acc = engine.state.accounts[acc_id]
+        pos = acc.position
 
-    # Rule R-W1: iterate accounts except LIQ in ascending account-id order
-    sorted_accounts = sorted([a for a in state.accounts if a != "LIQ"])
-
-    for acc_id in sorted_accounts:
-        acc = state.accounts[acc_id]
-
-        # Rule R-W2: position == 0 is never in breach
-        if acc.position == 0:
+        # R-W2: Position 0 is never in breach
+        if pos == 0:
             continue
 
-        # Breach calculation
-        avail = acc.free_cash + acc.position * state.mark_price
-        req = ceil_div(abs(acc.position) * state.mark_price * cfg.maint_bps, 10_000)
+        # Check breach condition
+        # avail = free_cash + position * mark_price
+        # req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)
+        def is_breached(a: Any) -> bool:
+            avail = a.free_cash + (a.position * engine.state.mark_price)
+            req = ceil_div(abs(a.position) * engine.state.mark_price * engine.cfg.MAINT_BPS, 10000)
+            return avail < req
 
-        if avail >= req:
+        if not is_breached(acc):
             continue
 
-        # Rule R-W3: Stage 1 cancel resting orders in ascending prio_seq order
-        orders = get_account_orders(state, acc_id)
+        # Stage 1: Cancel resting orders
+        # R-W3: Cancel in ascending prio_seq order
+        orders = get_account_orders(engine.state, acc_id)
         for o in orders:
-            remove_order(state, o.order_id)
-            acc.locked_margin -= o.lock
-            acc.free_cash += o.lock
-            o.lock = 0
-            reports.append(Report.cancelled(o.order_id, "RISK"))
+            # Each cancel releases the lock to free_cash
+            # Note: orders in book.py are already filtered by leaves > 0
+            # R-W3: reports CANCELLED(order_id, RISK)
+            reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))
+            # Release the lock associated with this specific order
+            # The rule says "Each cancel releases the lock to free_cash"
+            # The amount to release is the 'lock' field of the order.
+            release_lock(engine.state, acc_id, o.lock)
+            remove_order(engine.state, o.order_id)
 
-        # Rule R-W4: re-evaluate breach test with new free_cash
-        new_avail = acc.free_cash + acc.position * state.mark_price
-        if new_avail >= req:
-            # Breach resolved by stage 1
+        # R-W4: Re-compute breach test after Stage 1
+        if not is_breached(acc):
             continue
 
-        # Rule R-W5: Stage 2 liquidate whole position at mark_price against LIQ
-        orig_position = acc.position
-        liq_account = state.accounts["LIQ"]
+        # Stage 2: Liquidation
+        # R-W5: Liquidate whole position at mark_price against LIQ
+        orig_position = pos
+        mark_price = engine.state.mark_price
 
         if orig_position > 0:
-            # Account sells position to LIQ
-            transfer_amount = orig_position * state.mark_price
-            acc.free_cash += transfer_amount
-            liq_account.free_cash -= transfer_amount
-            acc.position = 0
-            liq_account.position += orig_position
+            # Long: account sells position units to LIQ.
+            # Account receives pos * mark_price. LIQ pays.
+            notional = orig_position * mark_price
+            transfer_cash(engine.state, "LIQ", acc_id, notional)
+            adjust_position(engine.state, "LIQ", orig_position)
         else:
-            # Account buys abs(position) from LIQ
-            transfer_amount = abs(orig_position) * state.mark_price
-            acc.free_cash -= transfer_amount
-            liq_account.free_cash += transfer_amount
-            acc.position = 0
-            liq_account.position += orig_position  # orig_position is negative
+            # Short: account buys abs(pos) units from LIQ.
+            # Account pays abs(pos) * mark_price. LIQ receives.
+            notional = abs(orig_position) * mark_price
+            transfer_cash(engine.state, acc_id, "LIQ", notional)
+            adjust_position(engine.state, "LIQ", orig_position)
 
-        reports.append(Report.liquidated(acc_id, orig_position))
+        # Position of account becomes 0
+        acc.position = 0
+        acc.locked_margin = 0  # Implicitly, no more margin can be locked if position is 0
+        # Note: Since we just liquidated, we should ensure any residual lock/free_cash
+        # logic is handled. The rules say "position becomes 0". 
+        # Since we are in Stage 2, the account was in breach. 
+        # After liquidation, pos=0, so req=0. avail = free_cash. 
+        # As long as free_cash >= 0, we are fine.
+        
+        # R-W5: report LIQUIDATED(account, qty)
+        reports.append(Report.liquidated(account=acc_id, qty=orig_position))
 
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
````
