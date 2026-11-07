# flash_lite · f5_basket_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemini-3.1-flash-lite` / `None` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | feedback_loop |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 25484 / 1934 |
| Latency (s) | 9.027411937713623 |
| Stop reason | – |
| Timestamp | 2026-11-06T07:19:59.612846+00:00 |
| Prompt | [`prompt.txt`](../../results/feedback/raw/flash_lite/f5_basket_b/0/prompt.txt) (sha256 `7e553cc067af8c79…`) |
| Raw files | [`results/feedback/raw/flash_lite/f5_basket_b/0/`](../../results/feedback/raw/flash_lite/f5_basket_b/0) |

## Feedback-loop turns

| Turn | Score | Passed | First failure |
|---|---|---|---|
| 0 | 0.3875 | False | D1 event 2 report differs from reference |
| 1 | 0.3875 | False | D1 event 2 report differs from reference |
| 2 | 1.0 | True | –  |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f5_basket_b/basket.py
+++ model/exchange_core/handlers/basket.py
@@ -1,27 +1,17 @@
 """exchange_core/handlers/basket.py
-Handle atomic BASKET event execution with rollback.
+Handler for atomic multi-leg basket orders.
 Rules R-A1 to R-A5. Target for task f5_basket_b.
 """
 from exchange_core.types import Event, Report
+from exchange_core.handlers.new_limit import handle_new_limit
 
 
 def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Process an atomic multi-leg basket order.
+    """Process a BASKET event with all-or-nothing rollback semantics."""
+    snapshot = engine.state.snapshot()
+    all_reports = []
 
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
+    for i, leg in enumerate(event.legs):
         leg_event = Event(
             kind="NEW_LIMIT",
             account=event.account,
@@ -31,26 +21,43 @@
             flag=leg.flag,
         )
 
-        leg_reports = engine.dispatch(leg_event)
+        leg_reports = handle_new_limit(engine, leg_event)
+        
+        # Check if the leg failed (Rule R-A3)
+        failed = False
+        
+        # A rejected leg fails
+        if any(r.kind == "REJECTED" for r in leg_reports):
+            failed = True
+        
+        # IOC leg check: must be fully filled (leaves == 0)
+        if not failed and leg.flag == "IOC":
+            # Check for IOC_REMAINDER which is a rejection-like failure
+            if any(r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER" for r in leg_reports):
+                failed = True
+            else:
+                # Must have been accepted, but if leaves > 0, it means it didn't fully fill
+                # (Engine usually returns Accepted then Fill reports)
+                accepted_id = next((r.order_id for r in leg_reports if r.kind == "ACCEPTED"), None)
+                if accepted_id is not None:
+                    order = engine.state.orders.get(accepted_id)
+                    if order is not None and order.leaves > 0:
+                        failed = True
+                else:
+                    # If not accepted, it must have failed (e.g. margin)
+                    failed = True
 
-        # Rule R-A3: leg success evaluation
-        # 1. Any rejection fails the leg
-        if any(r.kind == "REJECTED" for r in leg_reports):
-            engine.state.restore(snap)
-            return [Report.basket_rolled_back(leg_index)]
+        # POST_ONLY leg check: must not cross.
+        # If it crosses, engine returns REJECTED
+        if not failed and leg.flag == "POST_ONLY":
+            if not any(r.kind == "ACCEPTED" for r in leg_reports):
+                failed = True
 
-        # 2. IOC leg must have leaves == 0 after matching (cannot have IOC_REMAINDER)
-        if leg.flag == "IOC":
-            has_ioc_cancel = any(
-                r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"
-                for r in leg_reports
-            )
-            if has_ioc_cancel:
-                engine.state.restore(snap)
-                return [Report.basket_rolled_back(leg_index)]
+        if failed:
+            engine.state.restore(snapshot)
+            return [Report.basket_rolled_back(leg_index=i)]
 
-        all_leg_reports.extend(leg_reports)
+        all_reports.extend(leg_reports)
 
-    # Rule R-A5: all legs succeeded
-    all_leg_reports.append(Report.basket_committed())
-    return all_leg_reports
+    all_reports.append(Report.basket_committed())
+    return all_reports
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
from exchange_core.types import Event, Report
from exchange_core.handlers.new_limit import handle_new_limit


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a BASKET event with all-or-nothing rollback semantics."""
    snapshot = engine.state.snapshot()
    all_reports = []

    for i, leg in enumerate(event.legs):
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag,
        )

        leg_reports = handle_new_limit(engine, leg_event)
        
        # Check if the leg failed (Rule R-A3)
        failed = False
        
        # A rejected leg fails
        if any(r.kind == "REJECTED" for r in leg_reports):
            failed = True
        
        # IOC leg check: must be fully filled (leaves == 0)
        if not failed and leg.flag == "IOC":
            # Check for IOC_REMAINDER which is a rejection-like failure
            if any(r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER" for r in leg_reports):
                failed = True
            else:
                # Must have been accepted, but if leaves > 0, it means it didn't fully fill
                # (Engine usually returns Accepted then Fill reports)
                accepted_id = next((r.order_id for r in leg_reports if r.kind == "ACCEPTED"), None)
                if accepted_id is not None:
                    order = engine.state.orders.get(accepted_id)
                    if order is not None and order.leaves > 0:
                        failed = True
                else:
                    # If not accepted, it must have failed (e.g. margin)
                    failed = True

        # POST_ONLY leg check: must not cross.
        # If it crosses, engine returns REJECTED
        if not failed and leg.flag == "POST_ONLY":
            if not any(r.kind == "ACCEPTED" for r in leg_reports):
                failed = True

        if failed:
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index=i)]

        all_reports.extend(leg_reports)

    all_reports.append(Report.basket_committed())
    return all_reports
```
````
