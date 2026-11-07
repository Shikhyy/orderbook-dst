# mistral_large · f7_funding_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `mistral-large-4` / `mistral-large-4` |
| Settings | `{"max_tokens": 16000, "base_url": "https://api.mistral.ai/v1", "api_key_env": "MISTRAL_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 5842 / 1608 |
| Latency (s) | 16.58648705482483 |
| Stop reason | stop |
| Timestamp | 2026-11-04T12:21:26.121996+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/mistral_large/f7_funding_b/0/prompt.txt) (sha256 `881f6ab33c3b2758…`) |
| Raw files | [`results/main/raw/mistral_large/f7_funding_b/0/`](../../results/main/raw/mistral_large/f7_funding_b/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f7_funding_b/funding.py
+++ model/exchange_core/handlers/funding.py
@@ -1,43 +1,55 @@
 """exchange_core/handlers/funding.py
-Handle FUNDING event: periodic funding payments between long and short positions.
-Rules R-Y1 to R-Y5. Reference only.
+Handler for FUNDING events: funding payments, fee-vault residual and waterfall.
+Rules R-Y1 to R-Y5. Target for task f7_funding_b.
 """
 from exchange_core.intmath import round_half_even
 from exchange_core.types import Event, Report
 
-MAX_FUNDING_PPM = 3_000
-
 
 def handle_funding(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Apply funding payments, then run the margin waterfall at the current mark price."""
+    """Process a FUNDING event."""
     state = engine.state
     ppm = engine.cfg.ppm
 
-    # Rule R-Y1: the rate is clamped to +/- MAX_FUNDING_PPM
-    rate = max(-MAX_FUNDING_PPM, min(MAX_FUNDING_PPM, event.bps))
+    # R-Y1: clamp the funding rate to [-3000, 3000].
+    rate = max(-3000, min(3000, event.bps))
 
-    # Rule R-Y2: payments for every account with a position, ascending account id
-    residual = 0
-    paid = 0
+    total_paid = 0
+    total_received = 0
+    n = 0
+
+    # R-Y2: if rate != 0, process every account with a non-zero position,
+    # in ascending account-id order.
     if rate != 0:
-        for acc_id in sorted(state.accounts):
-            acc = state.accounts[acc_id]
-            if acc.position == 0:
+        mark_price = state.mark_price
+        for account_id in sorted(state.accounts):
+            account = state.accounts[account_id]
+            if account.position == 0:
                 continue
-            notional = abs(acc.position) * state.mark_price
-            amount = round_half_even(notional * abs(rate), ppm)  # rounds |x|; sign applied below
-            pays = (acc.position > 0) == (rate > 0)
-            payment = amount if pays else -amount
-            acc.free_cash -= payment
-            residual += payment
-            paid += 1
 
-    # Rule R-Y3: the rounding residual goes to the fee vault
-    state.fee_vault += residual
+            n += 1
+            notional = abs(account.position) * mark_price
+            amount = round_half_even(notional * abs(rate), ppm)
 
-    # Rule R-Y4: FUNDING_APPLIED report
-    reports = [Report(kind="FUNDING_APPLIED", bps=rate, qty=paid)]
+            pays = (account.position > 0 and rate > 0) or (
+                account.position < 0 and rate < 0
+            )
+            if pays:
+                account.free_cash -= amount
+                total_paid += amount
+            else:
+                account.free_cash += amount
+                total_received += amount
 
-    # Rule R-Y5: always run the waterfall at the current mark price
-    reports.extend(engine.dispatch(Event(kind="PRICE_SHOCK", mark_price=state.mark_price)))
+    # R-Y3: book the net rounding difference in the fee vault.
+    state.fee_vault += total_paid - total_received
+
+    # R-Y4: first report is FUNDING_APPLIED.
+    reports = [Report(kind="FUNDING_APPLIED", bps=rate, qty=n)]
+
+    # R-Y5: always run the margin waterfall at the current mark price.
+    reports.extend(
+        engine.dispatch(Event(kind="PRICE_SHOCK", mark_price=state.mark_price))
+    )
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
from exchange_core.intmath import round_half_even
from exchange_core.types import Event, Report


def handle_funding(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a FUNDING event."""
    state = engine.state
    ppm = engine.cfg.ppm

    # R-Y1: clamp the funding rate to [-3000, 3000].
    rate = max(-3000, min(3000, event.bps))

    total_paid = 0
    total_received = 0
    n = 0

    # R-Y2: if rate != 0, process every account with a non-zero position,
    # in ascending account-id order.
    if rate != 0:
        mark_price = state.mark_price
        for account_id in sorted(state.accounts):
            account = state.accounts[account_id]
            if account.position == 0:
                continue

            n += 1
            notional = abs(account.position) * mark_price
            amount = round_half_even(notional * abs(rate), ppm)

            pays = (account.position > 0 and rate > 0) or (
                account.position < 0 and rate < 0
            )
            if pays:
                account.free_cash -= amount
                total_paid += amount
            else:
                account.free_cash += amount
                total_received += amount

    # R-Y3: book the net rounding difference in the fee vault.
    state.fee_vault += total_paid - total_received

    # R-Y4: first report is FUNDING_APPLIED.
    reports = [Report(kind="FUNDING_APPLIED", bps=rate, qty=n)]

    # R-Y5: always run the margin waterfall at the current mark price.
    reports.extend(
        engine.dispatch(Event(kind="PRICE_SHOCK", mark_price=state.mark_price))
    )

    return reports
```
````
