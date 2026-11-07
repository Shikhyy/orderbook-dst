# gemma_26b · f4_waterfall_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemma-4-26b-a4b-it` / `None` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | feedback_loop |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 24692 / 3258 |
| Latency (s) | 72.79193902015686 |
| Stop reason | – |
| Timestamp | 2026-11-05T17:55:35.324967+00:00 |
| Prompt | [`prompt.txt`](../../results/feedback/raw/gemma_26b/f4_waterfall_b/0/prompt.txt) (sha256 `efc0519d18c2ffce…`) |
| Raw files | [`results/feedback/raw/gemma_26b/f4_waterfall_b/0/`](../../results/feedback/raw/gemma_26b/f4_waterfall_b/0) |

## Feedback-loop turns

| Turn | Score | Passed | First failure |
|---|---|---|---|
| 0 | 0.1889 | False | D1 event 7 report differs from reference |
| 1 | 1.0 | True | –  |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f4_waterfall_b/shock.py
+++ model/exchange_core/handlers/shock.py
@@ -1,80 +1,74 @@
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
-
-    Rules R-W1 to R-W6:
-    1. Set mark_price. Emit MARK_SET.
-    2. Iterate over accounts (except LIQ) in ascending order.
-    3. Stage 1: if breach, cancel resting orders in ascending prio_seq order.
-    4. Stage 2: if still in breach, liquidate position against LIQ.
-    """
+def handle_shock(engine: Any, event: Event) -> list[Report]:  # type: ignore # noqa: F821
+    """Process PRICE_SHOCK and run the margin waterfall for all breached accounts."""
     state = engine.state
     cfg = engine.cfg
-    reports: list[Report] = []
 
-    # Rule R-W1: set mark_price
+    # R-W1: Set mark price
     state.mark_price = event.mark_price
-    reports.append(Report.mark_set(event.mark_price))
+    reports: list[Report] = [Report.mark_set(mark_price=event.mark_price)]
 
-    # Rule R-W1: iterate accounts except LIQ in ascending account-id order
-    sorted_accounts = sorted([a for a in state.accounts if a != "LIQ"])
+    # Sort account IDs to process in ascending order (except LIQ)
+    account_ids = sorted([acc_id for acc_id in state.accounts if acc_id != "LIQ"])
 
-    for acc_id in sorted_accounts:
+    def is_in_breach(acc_id: str, current_mark_price: int) -> bool:
         acc = state.accounts[acc_id]
+        if acc.position == 0:
+            return False
+        avail = acc.free_cash + (acc.position * current_mark_price)
+        # req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)
+        req = ceil_div(abs(acc.position) * current_mark_price * cfg.MAINT_BPS, 10000)
+        return avail < req
 
-        # Rule R-W2: position == 0 is never in breach
-        if acc.position == 0:
+    for acc_id in account_ids:
+        # R-W2: Check breach
+        if not is_in_breach(acc_id, state.mark_price):
             continue
 
-        # Breach calculation
-        avail = acc.free_cash + acc.position * state.mark_price
-        req = ceil_div(abs(acc.position) * state.mark_price * cfg.maint_bps, 10_000)
+        # Stage 1: Cancel resting orders
+        orders = get_account_orders(state, acc_id)
+        # R-W3: Cancel in ascending prio_seq order
+        for o in orders:
+            # R-W3: Each cancel releases the lock to free_cash
+            release_lock(state, acc_id, o.lock)
+            remove_order(state, o.order_id)
+            reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))
 
-        if avail >= req:
+        # R-W4: Re-test after stage 1
+        if not is_in_breach(acc_id, state.mark_price):
             continue
 
-        # Rule R-W3: Stage 1 cancel resting orders in ascending prio_seq order
-        orders = get_account_orders(state, acc_id)
-        for o in orders:
-            remove_order(state, o.order_id)
-            acc.locked_margin -= o.lock
-            acc.free_cash += o.lock
-            o.lock = 0
-            reports.append(Report.cancelled(o.order_id, "RISK"))
+        # Stage 2: Liquidation
+        # R-W5: Liquidate whole position at mark_price against LIQ.
+        acc = state.accounts[acc_id]
+        orig_pos = acc.position
+        liq_acc_id = "LIQ"
 
-        # Rule R-W4: re-evaluate breach test with new free_cash
-        new_avail = acc.free_cash + acc.position * state.mark_price
-        if new_avail >= req:
-            # Breach resolved by stage 1
-            continue
+        if orig_pos > 0:
+            # Account sells orig_pos units to LIQ. 
+            # Account receives orig_pos * mark_price. LIQ pays the same amount.
+            notional = orig_pos * state.mark_price
+            transfer_cash(state, liq_acc_id, acc_id, notional)
+            adjust_position(state, liq_acc_id, orig_pos)
+        else:
+            # Account buys abs(orig_pos) units from LIQ. 
+            # Account pays abs(orig_pos) * mark_price. LIQ receives the same amount.
+            notional = abs(orig_pos) * state.mark_price
+            transfer_cash(state, acc_id, liq_acc_id, notional)
+            adjust_position(state, liq_acc_id, orig_pos)
 
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
+        # Account position becomes 0.
+        adjust_position(state, acc_id, -orig_pos)
+        reports.append(Report.liquidated(account=acc_id, qty=orig_pos))
 
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
    state = engine.state
    cfg = engine.cfg

    # R-W1: Set mark price
    state.mark_price = event.mark_price
    reports: list[Report] = [Report.mark_set(mark_price=event.mark_price)]

    # Sort account IDs to process in ascending order (except LIQ)
    account_ids = sorted([acc_id for acc_id in state.accounts if acc_id != "LIQ"])

    def is_in_breach(acc_id: str, current_mark_price: int) -> bool:
        acc = state.accounts[acc_id]
        if acc.position == 0:
            return False
        avail = acc.free_cash + (acc.position * current_mark_price)
        # req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)
        req = ceil_div(abs(acc.position) * current_mark_price * cfg.MAINT_BPS, 10000)
        return avail < req

    for acc_id in account_ids:
        # R-W2: Check breach
        if not is_in_breach(acc_id, state.mark_price):
            continue

        # Stage 1: Cancel resting orders
        orders = get_account_orders(state, acc_id)
        # R-W3: Cancel in ascending prio_seq order
        for o in orders:
            # R-W3: Each cancel releases the lock to free_cash
            release_lock(state, acc_id, o.lock)
            remove_order(state, o.order_id)
            reports.append(Report.cancelled(order_id=o.order_id, reason="RISK"))

        # R-W4: Re-test after stage 1
        if not is_in_breach(acc_id, state.mark_price):
            continue

        # Stage 2: Liquidation
        # R-W5: Liquidate whole position at mark_price against LIQ.
        acc = state.accounts[acc_id]
        orig_pos = acc.position
        liq_acc_id = "LIQ"

        if orig_pos > 0:
            # Account sells orig_pos units to LIQ. 
            # Account receives orig_pos * mark_price. LIQ pays the same amount.
            notional = orig_pos * state.mark_price
            transfer_cash(state, liq_acc_id, acc_id, notional)
            adjust_position(state, liq_acc_id, orig_pos)
        else:
            # Account buys abs(orig_pos) units from LIQ. 
            # Account pays abs(orig_pos) * mark_price. LIQ receives the same amount.
            notional = abs(orig_pos) * state.mark_price
            transfer_cash(state, acc_id, liq_acc_id, notional)
            adjust_position(state, liq_acc_id, orig_pos)

        # Account position becomes 0.
        adjust_position(state, acc_id, -orig_pos)
        reports.append(Report.liquidated(account=acc_id, qty=orig_pos))

    return reports
```
````
