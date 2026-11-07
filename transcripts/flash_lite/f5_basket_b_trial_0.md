# flash_lite · f5_basket_b · trial 0 — failure (lowest score)

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemini-3.1-flash-lite` / `gemini-3.1-flash-lite` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 0.3875 (1.0 / 0.625 / 0.0) |
| Outcome | D1 |
| Error | – |
| Tokens in / out | 7988 / 551 |
| Latency (s) | 3.4001779556274414 |
| Stop reason | stop |
| Timestamp | 2026-11-04T07:32:04.372321+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/flash_lite/f5_basket_b/0/prompt.txt) (sha256 `7e553cc067af8c79…`) |
| Raw files | [`results/main/raw/flash_lite/f5_basket_b/0/`](../../results/main/raw/flash_lite/f5_basket_b/0) |

## First failure (hidden trace)

- Seed 8000, event 2: **D1** — Report mismatch
- Message: `event 2 report differs from reference`

```json
{
  "expected": [
    {
      "kind": "BASKET_ROLLED_BACK",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 0,
      "taker_order_id": 0,
      "account": "",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    }
  ],
  "actual": [
    {
      "kind": "ACCEPTED",
      "order_id": 2,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 0,
      "taker_order_id": 0,
      "account": "",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "CANCELLED",
      "order_id": 2,
      "reason": "IOC_REMAINDER",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 0,
      "taker_order_id": 0,
      "account": "",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "ACCEPTED",
      "order_id": 3,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 0,
      "taker_order_id": 0,
      "account": "",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "FILL",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 3,
      "sell_order_id": 1,
      "price": 99990000,
      "qty": 4,
      "taker_order_id": 3,
      "account": "",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "ACCEPTED",
      "order_id": 4,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 0,
      "taker_order_id": 0,
      "account": "",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "FILL",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 4,
      "sell_order_id": 1,
      "price": 99990000,
      "qty": 2,
      "taker_order_id": 4,
      "account": "",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "BASKET_COMMITTED",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 0,
      "taker_order_id": 0,
      "account": "",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    }
  ]
}
```

## Labels on all failing hidden seeds

D1×20 (over 20 failing seeds of 20)

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f5_basket_b/basket.py
+++ model/exchange_core/handlers/basket.py
@@ -1,56 +1,62 @@
 """exchange_core/handlers/basket.py
-Handle atomic BASKET event execution with rollback.
+Handler for atomic multi-leg basket orders.
 Rules R-A1 to R-A5. Target for task f5_basket_b.
 """
-from exchange_core.types import Event, Report
+from typing import Any
+from exchange_core.types import Event, Report, Order
+from exchange_core.book import get_order
 
 
-def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process an atomic multi-leg basket order.
-
-    Rules R-A1 to R-A5:
-    - R-A2: Take snapshot before leg 1. Process each leg in order as NEW_LIMIT.
-    - R-A3: An IOC leg succeeds if accepted and leaves is 0 after matching.
-            A POST_ONLY leg succeeds if accepted. A rejected leg fails.
-    - R-A4: If a leg fails, restore snapshot. Report BASKET_ROLLED_BACK(leg_index).
-            Discard reports of earlier legs.
-    - R-A5: If all legs succeed, report all leg reports in order + BASKET_COMMITTED.
-    """
-    # Rule R-A2: snapshot complete state before processing leg 1
-    snap = engine.state.snapshot()
-
-    all_leg_reports: list[Report] = []
-
-    for leg_index, leg in enumerate(event.legs):
+def handle_basket(engine: Any, event: Event) -> list[Report]:
+    """Process a BASKET event with all-or-nothing rollback semantics."""
+    snapshot = engine.state.snapshot()
+    reports = []
+    
+    for i, leg in enumerate(event.legs):
         leg_event = Event(
             kind="NEW_LIMIT",
             account=event.account,
             side=leg.side,
             price=leg.price,
             qty=leg.qty,
-            flag=leg.flag,
+            flag=leg.flag
         )
-
+        
         leg_reports = engine.dispatch(leg_event)
-
-        # Rule R-A3: leg success evaluation
-        # 1. Any rejection fails the leg
-        if any(r.kind == "REJECTED" for r in leg_reports):
-            engine.state.restore(snap)
-            return [Report.basket_rolled_back(leg_index)]
-
-        # 2. IOC leg must have leaves == 0 after matching (cannot have IOC_REMAINDER)
-        if leg.flag == "IOC":
-            has_ioc_cancel = any(
-                r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"
-                for r in leg_reports
-            )
-            if has_ioc_cancel:
-                engine.state.restore(snap)
-                return [Report.basket_rolled_back(leg_index)]
-
-        all_leg_reports.extend(leg_reports)
-
-    # Rule R-A5: all legs succeeded
-    all_leg_reports.append(Report.basket_committed())
-    return all_leg_reports
+        
+        # Check if leg failed
+        failed = False
+        
+        # Rule R-A3: Verify Acceptance and success condition
+        # A leg fails if not accepted or violates specific logic (IOC/POST_ONLY)
+        accepted = False
+        for r in leg_reports:
+            if r.kind == "ACCEPTED":
+                accepted = True
+                order_id = r.order_id
+                break
+        
+        if not accepted:
+            failed = True
+        else:
+            # Check for specific failure based on flag
+            if leg.flag == "IOC":
+                # IOC succeeds if leaves is 0 (fully filled)
+                order = get_order(engine.state, order_id)
+                if order is not None and order.leaves > 0:
+                    failed = True
+            elif leg.flag == "POST_ONLY":
+                # POST_ONLY fails if it crossed (must be resting)
+                order = get_order(engine.state, order_id)
+                # If it didn't stay as an order, it crossed and was filled/cancelled
+                if order is None:
+                    failed = True
+                    
+        if failed:
+            engine.state.restore(snapshot)
+            return [Report.basket_rolled_back(leg_index=i)]
+        
+        reports.extend(leg_reports)
+    
+    reports.append(Report.basket_committed())
+    return reports
```

## Author analysis

_Write after reading the reply: what the model got wrong and why, or whether the grader rejected a valid answer._

## Model reply (verbatim)

````text
### FILE: exchange_core/handlers/basket.py
```python
"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from typing import Any
from exchange_core.types import Event, Report, Order
from exchange_core.book import get_order


def handle_basket(engine: Any, event: Event) -> list[Report]:
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
        
        # Check if leg failed
        failed = False
        
        # Rule R-A3: Verify Acceptance and success condition
        # A leg fails if not accepted or violates specific logic (IOC/POST_ONLY)
        accepted = False
        for r in leg_reports:
            if r.kind == "ACCEPTED":
                accepted = True
                order_id = r.order_id
                break
        
        if not accepted:
            failed = True
        else:
            # Check for specific failure based on flag
            if leg.flag == "IOC":
                # IOC succeeds if leaves is 0 (fully filled)
                order = get_order(engine.state, order_id)
                if order is not None and order.leaves > 0:
                    failed = True
            elif leg.flag == "POST_ONLY":
                # POST_ONLY fails if it crossed (must be resting)
                order = get_order(engine.state, order_id)
                # If it didn't stay as an order, it crossed and was filled/cancelled
                if order is None:
                    failed = True
                    
        if failed:
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index=i)]
        
        reports.extend(leg_reports)
    
    reports.append(Report.basket_committed())
    return reports
```
````
