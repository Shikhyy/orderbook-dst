# nemotron_ultra · f7_funding_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `nvidia/nemotron-3-ultra-550b-a55b:free` / `nvidia/nemotron-3-ultra-550b-a55b:free` |
| Settings | `{"max_tokens": 16000, "base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 6067 / 1901 |
| Latency (s) | 32.590177059173584 |
| Stop reason | stop |
| Timestamp | 2026-11-05T08:17:16.166734+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/nemotron_ultra/f7_funding_b/0/prompt.txt) (sha256 `881f6ab33c3b2758…`) |
| Raw files | [`results/main/raw/nemotron_ultra/f7_funding_b/0/`](../../results/main/raw/nemotron_ultra/f7_funding_b/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f7_funding_b/funding.py
+++ model/exchange_core/handlers/funding.py
@@ -1,43 +1,59 @@
 """exchange_core/handlers/funding.py
-Handle FUNDING event: periodic funding payments between long and short positions.
-Rules R-Y1 to R-Y5. Reference only.
+Handler for FUNDING events: funding payments, fee-vault residual and waterfall.
+Rules R-Y1 to R-Y5. Target for task f7_funding_b.
 """
+from exchange_core.types import Event, Report
 from exchange_core.intmath import round_half_even
-from exchange_core.types import Event, Report
-
-MAX_FUNDING_PPM = 3_000
 
 
 def handle_funding(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
-    """Apply funding payments, then run the margin waterfall at the current mark price."""
+    """Process a FUNDING event."""
     state = engine.state
-    ppm = engine.cfg.ppm
+    cfg = engine.cfg
 
-    # Rule R-Y1: the rate is clamped to +/- MAX_FUNDING_PPM
-    rate = max(-MAX_FUNDING_PPM, min(MAX_FUNDING_PPM, event.bps))
+    # R-Y1: Clamp rate to [-3000, 3000]
+    rate = max(-3000, min(3000, event.bps))
 
-    # Rule R-Y2: payments for every account with a position, ascending account id
-    residual = 0
-    paid = 0
+    reports: list[Report] = []
+    n = 0  # number of accounts processed
+    net_payment = 0  # payments minus receipts
+
     if rate != 0:
-        for acc_id in sorted(state.accounts):
-            acc = state.accounts[acc_id]
-            if acc.position == 0:
-                continue
+        # R-Y2: Process every account with position != 0 in ascending account-id order
+        accounts_with_position = [
+            (acc_id, acc) for acc_id, acc in state.accounts.items()
+            if acc.position != 0
+        ]
+        accounts_with_position.sort(key=lambda x: x[0])  # sort by account_id ascending
+
+        n = len(accounts_with_position)
+
+        for acc_id, acc in accounts_with_position:
             notional = abs(acc.position) * state.mark_price
-            amount = round_half_even(notional * abs(rate), ppm)  # rounds |x|; sign applied below
-            pays = (acc.position > 0) == (rate > 0)
-            payment = amount if pays else -amount
-            acc.free_cash -= payment
-            residual += payment
-            paid += 1
+            amount = round_half_even(notional * abs(rate), cfg.ppm)
 
-    # Rule R-Y3: the rounding residual goes to the fee vault
-    state.fee_vault += residual
+            is_long = acc.position > 0
+            is_short = acc.position < 0
 
-    # Rule R-Y4: FUNDING_APPLIED report
-    reports = [Report(kind="FUNDING_APPLIED", bps=rate, qty=paid)]
+            # Pays when (long and rate > 0) or (short and rate < 0)
+            pays = (is_long and rate > 0) or (is_short and rate < 0)
 
-    # Rule R-Y5: always run the waterfall at the current mark price
-    reports.extend(engine.dispatch(Event(kind="PRICE_SHOCK", mark_price=state.mark_price)))
+            if pays:
+                acc.free_cash -= amount
+                net_payment += amount
+            else:
+                acc.free_cash += amount
+                net_payment -= amount
+
+    # R-Y3: Add net of all payments to fee_vault
+    state.fee_vault += net_payment
+
+    # R-Y4: First report
+    reports.append(Report(kind="FUNDING_APPLIED", bps=rate, qty=n))
+
+    # R-Y5: Run margin waterfall via PRICE_SHOCK dispatch
+    price_shock_event = Event(kind="PRICE_SHOCK", mark_price=state.mark_price)
+    shock_reports = engine.dispatch(price_shock_event)
+    reports.extend(shock_reports)
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
from exchange_core.types import Event, Report
from exchange_core.intmath import round_half_even


def handle_funding(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a FUNDING event."""
    state = engine.state
    cfg = engine.cfg

    # R-Y1: Clamp rate to [-3000, 3000]
    rate = max(-3000, min(3000, event.bps))

    reports: list[Report] = []
    n = 0  # number of accounts processed
    net_payment = 0  # payments minus receipts

    if rate != 0:
        # R-Y2: Process every account with position != 0 in ascending account-id order
        accounts_with_position = [
            (acc_id, acc) for acc_id, acc in state.accounts.items()
            if acc.position != 0
        ]
        accounts_with_position.sort(key=lambda x: x[0])  # sort by account_id ascending

        n = len(accounts_with_position)

        for acc_id, acc in accounts_with_position:
            notional = abs(acc.position) * state.mark_price
            amount = round_half_even(notional * abs(rate), cfg.ppm)

            is_long = acc.position > 0
            is_short = acc.position < 0

            # Pays when (long and rate > 0) or (short and rate < 0)
            pays = (is_long and rate > 0) or (is_short and rate < 0)

            if pays:
                acc.free_cash -= amount
                net_payment += amount
            else:
                acc.free_cash += amount
                net_payment -= amount

    # R-Y3: Add net of all payments to fee_vault
    state.fee_vault += net_payment

    # R-Y4: First report
    reports.append(Report(kind="FUNDING_APPLIED", bps=rate, qty=n))

    # R-Y5: Run margin waterfall via PRICE_SHOCK dispatch
    price_shock_event = Event(kind="PRICE_SHOCK", mark_price=state.mark_price)
    shock_reports = engine.dispatch(price_shock_event)
    reports.extend(shock_reports)

    return reports
```
````
