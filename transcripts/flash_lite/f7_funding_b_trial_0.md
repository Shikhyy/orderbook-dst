# flash_lite · f7_funding_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemini-3.1-flash-lite` / `gemini-3.1-flash-lite` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 6697 / 611 |
| Latency (s) | 6.260421991348267 |
| Stop reason | stop |
| Timestamp | 2026-11-04T12:29:42.024885+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/flash_lite/f7_funding_b/0/prompt.txt) (sha256 `881f6ab33c3b2758…`) |
| Raw files | [`results/main/raw/flash_lite/f7_funding_b/0/`](../../results/main/raw/flash_lite/f7_funding_b/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f7_funding_b/funding.py
+++ model/exchange_core/handlers/funding.py
@@ -1,43 +1,61 @@
 """exchange_core/handlers/funding.py
-Handle FUNDING event: periodic funding payments between long and short positions.
-Rules R-Y1 to R-Y5. Reference only.
+Handler for FUNDING events: funding payments, fee-vault residual and waterfall.
+Rules R-Y1 to R-Y5. Target for task f7_funding_b.
 """
+from typing import Any
+from exchange_core.types import Event, Report
 from exchange_core.intmath import round_half_even
-from exchange_core.types import Event, Report
-
-MAX_FUNDING_PPM = 3_000
 
 
-def handle_funding(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Apply funding payments, then run the margin waterfall at the current mark price."""
-    state = engine.state
-    ppm = engine.cfg.ppm
+def handle_funding(engine: Any, event: Event) -> list[Report]:
+    """Process a FUNDING event."""
+    # R-Y1: Clamp the rate
+    rate = event.bps
+    if rate > 3000:
+        rate = 3000
+    elif rate < -3000:
+        rate = -3000
 
-    # Rule R-Y1: the rate is clamped to +/- MAX_FUNDING_PPM
-    rate = max(-MAX_FUNDING_PPM, min(MAX_FUNDING_PPM, event.bps))
+    reports = []
+    num_processed = 0
 
-    # Rule R-Y2: payments for every account with a position, ascending account id
-    residual = 0
-    paid = 0
     if rate != 0:
-        for acc_id in sorted(state.accounts):
-            acc = state.accounts[acc_id]
-            if acc.position == 0:
-                continue
-            notional = abs(acc.position) * state.mark_price
-            amount = round_half_even(notional * abs(rate), ppm)  # rounds |x|; sign applied below
-            pays = (acc.position > 0) == (rate > 0)
-            payment = amount if pays else -amount
-            acc.free_cash -= payment
-            residual += payment
-            paid += 1
+        # R-Y2: Process every account with position != 0 in ascending account-id order
+        account_ids = sorted(engine.state.accounts.keys())
+        net_payment = 0
+        ppm = engine.cfg.ppm
+        mark_price = engine.state.mark_price
 
-    # Rule R-Y3: the rounding residual goes to the fee vault
-    state.fee_vault += residual
+        for acc_id in account_ids:
+            account = engine.state.accounts[acc_id]
+            if account.position != 0:
+                num_processed += 1
+                notional = abs(account.position) * mark_price
+                amount = round_half_even(notional * abs(rate), ppm)
 
-    # Rule R-Y4: FUNDING_APPLIED report
-    reports = [Report(kind="FUNDING_APPLIED", bps=rate, qty=paid)]
+                # Determine if pay or receive
+                # Long: position > 0, Short: position < 0
+                # Pays if (long and rate > 0) or (short and rate < 0)
+                is_long = account.position > 0
+                is_short = account.position < 0
+                
+                pays = (is_long and rate > 0) or (is_short and rate < 0)
 
-    # Rule R-Y5: always run the waterfall at the current mark price
-    reports.extend(engine.dispatch(Event(kind="PRICE_SHOCK", mark_price=state.mark_price)))
+                if pays:
+                    account.free_cash -= amount
+                    net_payment += amount
+                else:
+                    account.free_cash += amount
+                    net_payment -= amount
+
+        # R-Y3: Add net of all payments to fee_vault
+        engine.state.fee_vault += net_payment
+
+    # R-Y4: First report
+    reports.append(Report(kind="FUNDING_APPLIED", bps=rate, qty=num_processed))
+
+    # R-Y5: Run margin waterfall
+    shock_event = Event(kind="PRICE_SHOCK", mark_price=engine.state.mark_price)
+    reports.extend(engine.dispatch(shock_event))
+
     return reports
```

## Author analysis

_Write after reading the reply: what the model got wrong and why, or whether the grader rejected a valid answer._

## Model reply (verbatim)

````text
### FILE: exchange_core/handlers/funding.py
```python
"""exchange_core/handlers/funding.py
Handler for FUNDING events: funding payments, fee-vault residual and waterfall.
Rules R-Y1 to R-Y5. Target for task f7_funding_b.
"""
from typing import Any
from exchange_core.types import Event, Report
from exchange_core.intmath import round_half_even


def handle_funding(engine: Any, event: Event) -> list[Report]:
    """Process a FUNDING event."""
    # R-Y1: Clamp the rate
    rate = event.bps
    if rate > 3000:
        rate = 3000
    elif rate < -3000:
        rate = -3000

    reports = []
    num_processed = 0

    if rate != 0:
        # R-Y2: Process every account with position != 0 in ascending account-id order
        account_ids = sorted(engine.state.accounts.keys())
        net_payment = 0
        ppm = engine.cfg.ppm
        mark_price = engine.state.mark_price

        for acc_id in account_ids:
            account = engine.state.accounts[acc_id]
            if account.position != 0:
                num_processed += 1
                notional = abs(account.position) * mark_price
                amount = round_half_even(notional * abs(rate), ppm)

                # Determine if pay or receive
                # Long: position > 0, Short: position < 0
                # Pays if (long and rate > 0) or (short and rate < 0)
                is_long = account.position > 0
                is_short = account.position < 0
                
                pays = (is_long and rate > 0) or (is_short and rate < 0)

                if pays:
                    account.free_cash -= amount
                    net_payment += amount
                else:
                    account.free_cash += amount
                    net_payment -= amount

        # R-Y3: Add net of all payments to fee_vault
        engine.state.fee_vault += net_payment

    # R-Y4: First report
    reports.append(Report(kind="FUNDING_APPLIED", bps=rate, qty=num_processed))

    # R-Y5: Run margin waterfall
    shock_event = Event(kind="PRICE_SHOCK", mark_price=engine.state.mark_price)
    reports.extend(engine.dispatch(shock_event))

    return reports
```
````
