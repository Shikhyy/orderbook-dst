# flash_lite · f8_adl_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemini-3.1-flash-lite` / `gemini-3.1-flash-lite` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 7690 / 705 |
| Latency (s) | 2.691904067993164 |
| Stop reason | stop |
| Timestamp | 2026-11-05T14:44:30.861798+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/flash_lite/f8_adl_b/0/prompt.txt) (sha256 `ac94d0d4f5f24be0…`) |
| Raw files | [`results/main/raw/flash_lite/f8_adl_b/0/`](../../results/main/raw/flash_lite/f8_adl_b/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f8_adl_b/bankruptcy.py
+++ model/exchange_core/handlers/bankruptcy.py
@@ -1,56 +1,69 @@
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
+    # R-L2: Fee Vault
     cover = min(deficit, max(0, state.fee_vault))
+    remaining = deficit - cover
     if cover > 0:
         state.fee_vault -= cover
-        victim.free_cash += cover
+        account.free_cash += cover
         reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
-
-    remaining = deficit - cover
+    
     if remaining == 0:
         return reports
 
-    # Rule R-L3: the rest is shared by the accounts on the other side of the liquidated position
-    weights: dict[str, int] = {}
-    for acc_id, acc in state.accounts.items():
-        if acc_id == "LIQ" or acc_id == account_id or acc.position == 0:
+    # R-L3: ADL Sharing
+    # Determine eligible accounts
+    eligible = []
+    for acc_id, acc_obj in state.accounts.items():
+        if acc_id == "LIQ" or acc_id == account_id:
             continue
-        if (acc.position > 0) != (pre_position > 0):
-            weights[acc_id] = abs(acc.position)
-
-    # Rule R-L4: nobody to share with, the loss stays as bad debt
-    if not weights:
+        if acc_obj.position != 0:
+            # Opposite sign check
+            if (pre_position > 0 and acc_obj.position < 0) or (pre_position < 0 and acc_obj.position > 0):
+                eligible.append((acc_id, abs(acc_obj.position)))
+    
+    if not eligible:
+        # R-L4: Bad Debt
         reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
         return reports
 
-    total = sum(weights.values())
-    shares = {acc_id: remaining * w // total for acc_id, w in weights.items()}
-    leftover = remaining - sum(shares.values())
-    ranked = sorted(weights, key=lambda a: (-weights[a], a))
-    for acc_id in ranked[:leftover]:
+    # Calculate shares
+    total_weight = sum(w for _, w in eligible)
+    
+    # Sort for distributing leftover: desc weight, then asc id
+    sorted_eligible = sorted(eligible, key=lambda x: (-x[1], x[0]))
+    
+    shares = {acc_id: (remaining * weight) // total_weight for acc_id, weight in eligible}
+    distributed = sum(shares.values())
+    leftover = remaining - distributed
+    
+    for i in range(leftover):
+        acc_id = sorted_eligible[i][0]
         shares[acc_id] += 1
-
-    for acc_id in sorted(shares):
-        if shares[acc_id] > 0:
-            state.accounts[acc_id].free_cash -= shares[acc_id]
-            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
-    victim.free_cash += remaining
+    
+    # Apply shares
+    account.free_cash += remaining
+    for acc_id, share in sorted(shares.items()):
+        if share > 0:
+            state.accounts[acc_id].free_cash -= share
+            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))
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
    
    # R-L2: Fee Vault
    cover = min(deficit, max(0, state.fee_vault))
    remaining = deficit - cover
    if cover > 0:
        state.fee_vault -= cover
        account.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
    
    if remaining == 0:
        return reports

    # R-L3: ADL Sharing
    # Determine eligible accounts
    eligible = []
    for acc_id, acc_obj in state.accounts.items():
        if acc_id == "LIQ" or acc_id == account_id:
            continue
        if acc_obj.position != 0:
            # Opposite sign check
            if (pre_position > 0 and acc_obj.position < 0) or (pre_position < 0 and acc_obj.position > 0):
                eligible.append((acc_id, abs(acc_obj.position)))
    
    if not eligible:
        # R-L4: Bad Debt
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    # Calculate shares
    total_weight = sum(w for _, w in eligible)
    
    # Sort for distributing leftover: desc weight, then asc id
    sorted_eligible = sorted(eligible, key=lambda x: (-x[1], x[0]))
    
    shares = {acc_id: (remaining * weight) // total_weight for acc_id, weight in eligible}
    distributed = sum(shares.values())
    leftover = remaining - distributed
    
    for i in range(leftover):
        acc_id = sorted_eligible[i][0]
        shares[acc_id] += 1
    
    # Apply shares
    account.free_cash += remaining
    for acc_id, share in sorted(shares.items()):
        if share > 0:
            state.accounts[acc_id].free_cash -= share
            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))
            
    return reports
```
````
