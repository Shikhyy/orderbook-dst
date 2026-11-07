# flash_lite · f8_adl_b · trial 2 — failure (lowest score)

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemini-3.1-flash-lite` / `gemini-3.1-flash-lite` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 0.1667 (0.8333333333333334 / 0.0 / 0.0) |
| Outcome | I1 |
| Error | – |
| Tokens in / out | 7690 / 798 |
| Latency (s) | 4.199351072311401 |
| Stop reason | stop |
| Timestamp | 2026-11-05T14:44:56.472714+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/flash_lite/f8_adl_b/2/prompt.txt) (sha256 `ac94d0d4f5f24be0…`) |
| Raw files | [`results/main/raw/flash_lite/f8_adl_b/2/`](../../results/main/raw/flash_lite/f8_adl_b/2) |

## First failure (hidden trace)

- Seed 11000, event 49: **I1** — No money created or destroyed
- Message: `total money 104332003554 != initial 104200000000`

```json
{
  "expected": 104200000000,
  "actual": 104332003554
}
```

## Labels on all failing hidden seeds

I1×20 (over 20 failing seeds of 20)

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f8_adl_b/bankruptcy.py
+++ model/exchange_core/handlers/bankruptcy.py
@@ -1,56 +1,80 @@
 """exchange_core/handlers/bankruptcy.py
-Bankruptcy procedure run after a liquidation: insurance draw, then pro-rata loss sharing.
-Rules R-L1 to R-L4. Reference only.
+Bankruptcy procedure after a liquidation: insurance draw, then loss sharing.
+Rules R-L1 to R-L5. Target for task f8_adl_b.
 """
 from exchange_core.types import Report
 
 
-def handle_bankruptcy(engine: "Engine", account_id: str, pre_position: int) -> list[Report]:  # type: ignore # noqa: F821
-    """Cover the negative cash of a just-liquidated account and return the reports."""
+def handle_bankruptcy(
+    engine: "Engine", account_id: str, pre_position: int  # type: ignore # noqa: F821
+) -> list[Report]:
+    """Cover the deficit of a just-liquidated account and return the reports in order."""
     state = engine.state
-    victim = state.accounts[account_id]
+    account = state.accounts[account_id]
+    deficit = max(0, -account.free_cash)
 
-    # Rule R-L1: the deficit is the negative cash that remains after liquidation
-    deficit = max(0, -victim.free_cash)
     if deficit == 0:
         return []
 
-    reports: list[Report] = []
-
-    # Rule R-L2: the fee vault (never below zero) pays first
+    reports = []
+    
+    # R-L2: Fee vault pays first
     cover = min(deficit, max(0, state.fee_vault))
+    remaining = deficit - cover
     if cover > 0:
         state.fee_vault -= cover
-        victim.free_cash += cover
+        account.free_cash += cover
         reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
 
-    remaining = deficit - cover
     if remaining == 0:
         return reports
 
-    # Rule R-L3: the rest is shared by the accounts on the other side of the liquidated position
-    weights: dict[str, int] = {}
+    # R-L3: Share remaining among eligible accounts
+    # Eligible: not LIQ, not account_id, position != 0, opposite sign to pre_position
+    eligible = []
     for acc_id, acc in state.accounts.items():
-        if acc_id == "LIQ" or acc_id == account_id or acc.position == 0:
+        if acc_id == "LIQ" or acc_id == account_id:
             continue
-        if (acc.position > 0) != (pre_position > 0):
-            weights[acc_id] = abs(acc.position)
+        if acc.position != 0 and (
+            (pre_position > 0 and acc.position < 0) or (pre_position < 0 and acc.position > 0)
+        ):
+            eligible.append((acc_id, abs(acc.position)))
 
-    # Rule R-L4: nobody to share with, the loss stays as bad debt
-    if not weights:
+    if not eligible:
+        # R-L4: No eligible accounts
+        account.free_cash += remaining
         reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
         return reports
 
-    total = sum(weights.values())
-    shares = {acc_id: remaining * w // total for acc_id, w in weights.items()}
-    leftover = remaining - sum(shares.values())
-    ranked = sorted(weights, key=lambda a: (-weights[a], a))
-    for acc_id in ranked[:leftover]:
-        shares[acc_id] += 1
-
-    for acc_id in sorted(shares):
-        if shares[acc_id] > 0:
-            state.accounts[acc_id].free_cash -= shares[acc_id]
-            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
-    victim.free_cash += remaining
+    total_weight = sum(w for _, w in eligible)
+    
+    # Calculate base shares
+    shares = []
+    total_assigned = 0
+    for acc_id, weight in eligible:
+        base = (remaining * weight) // total_weight
+        shares.append([acc_id, weight, base])
+        total_assigned += base
+    
+    leftover = remaining - total_assigned
+    
+    # R-L3: Sort for leftover distribution: Descending weight, then ascending account ID
+    shares.sort(key=lambda x: (-x[1], x[0]))
+    for i in range(leftover):
+        shares[i][2] += 1
+        
+    # Apply shares and collect reports
+    report_items = []
+    for acc_id, _, share in shares:
+        if share > 0:
+            state.accounts[acc_id].free_cash -= share
+            report_items.append((acc_id, share))
+    
+    account.free_cash += remaining
+    
+    # Report APPLIED in ascending order
+    report_items.sort(key=lambda x: x[0])
+    for acc_id, share in report_items:
+        reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))
+        
     return reports
```

## Author analysis

_Write after reading the reply: what the model got wrong and why, or whether the grader rejected a valid answer._

## Model reply (verbatim)

````text
### FILE: exchange_core/handlers/bankruptcy.py
```python
"""exchange_core/handlers/bankruptcy.py
Bankruptcy procedure after a liquidation: insurance draw, then loss sharing.
Rules R-L1 to R-L5. Target for task f8_adl_b.
"""
from exchange_core.types import Report


def handle_bankruptcy(
    engine: "Engine", account_id: str, pre_position: int  # type: ignore # noqa: F821
) -> list[Report]:
    """Cover the deficit of a just-liquidated account and return the reports in order."""
    state = engine.state
    account = state.accounts[account_id]
    deficit = max(0, -account.free_cash)

    if deficit == 0:
        return []

    reports = []
    
    # R-L2: Fee vault pays first
    cover = min(deficit, max(0, state.fee_vault))
    remaining = deficit - cover
    if cover > 0:
        state.fee_vault -= cover
        account.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))

    if remaining == 0:
        return reports

    # R-L3: Share remaining among eligible accounts
    # Eligible: not LIQ, not account_id, position != 0, opposite sign to pre_position
    eligible = []
    for acc_id, acc in state.accounts.items():
        if acc_id == "LIQ" or acc_id == account_id:
            continue
        if acc.position != 0 and (
            (pre_position > 0 and acc.position < 0) or (pre_position < 0 and acc.position > 0)
        ):
            eligible.append((acc_id, abs(acc.position)))

    if not eligible:
        # R-L4: No eligible accounts
        account.free_cash += remaining
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    total_weight = sum(w for _, w in eligible)
    
    # Calculate base shares
    shares = []
    total_assigned = 0
    for acc_id, weight in eligible:
        base = (remaining * weight) // total_weight
        shares.append([acc_id, weight, base])
        total_assigned += base
    
    leftover = remaining - total_assigned
    
    # R-L3: Sort for leftover distribution: Descending weight, then ascending account ID
    shares.sort(key=lambda x: (-x[1], x[0]))
    for i in range(leftover):
        shares[i][2] += 1
        
    # Apply shares and collect reports
    report_items = []
    for acc_id, _, share in shares:
        if share > 0:
            state.accounts[acc_id].free_cash -= share
            report_items.append((acc_id, share))
    
    account.free_cash += remaining
    
    # Report APPLIED in ascending order
    report_items.sort(key=lambda x: x[0])
    for acc_id, share in report_items:
        reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))
        
    return reports
```
````
