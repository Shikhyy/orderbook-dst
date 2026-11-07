# gemma_26b · f8_adl_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `gemma-4-26b-a4b-it` / `gemma-4-26b-a4b-it` |
| Settings | `{"max_tokens": 8000, "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key_env": "GEMINI_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 7690 / 825 |
| Latency (s) | 19.11126685142517 |
| Stop reason | stop |
| Timestamp | 2026-11-05T14:42:08.335262+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/gemma_26b/f8_adl_b/0/prompt.txt) (sha256 `ac94d0d4f5f24be0…`) |
| Raw files | [`results/main/raw/gemma_26b/f8_adl_b/0/`](../../results/main/raw/gemma_26b/f8_adl_b/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f8_adl_b/bankruptcy.py
+++ model/exchange_core/handlers/bankruptcy.py
@@ -1,56 +1,83 @@
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
+    x_acc = state.accounts[account_id]
+    deficit = max(0, -x_acc.free_cash)
 
-    # Rule R-L1: the deficit is the negative cash that remains after liquidation
-    deficit = max(0, -victim.free_cash)
     if deficit == 0:
         return []
 
-    reports: list[Report] = []
+    reports = []
 
-    # Rule R-L2: the fee vault (never below zero) pays first
+    # R-L2: Insurance Draw
     cover = min(deficit, max(0, state.fee_vault))
     if cover > 0:
         state.fee_vault -= cover
-        victim.free_cash += cover
+        x_acc.free_cash += cover
         reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
 
     remaining = deficit - cover
     if remaining == 0:
         return reports
 
-    # Rule R-L3: the rest is shared by the accounts on the other side of the liquidated position
-    weights: dict[str, int] = {}
+    # R-L3: Loss Sharing
+    eligible_accounts = []
+    total_weight = 0
     for acc_id, acc in state.accounts.items():
-        if acc_id == "LIQ" or acc_id == account_id or acc.position == 0:
+        if acc_id == "LIQ" or acc_id == account_id:
             continue
-        if (acc.position > 0) != (pre_position > 0):
-            weights[acc_id] = abs(acc.position)
+        if acc.position != 0 and (acc.position > 0) != (pre_position > 0):
+            weight = abs(acc.position)
+            eligible_accounts.append({"id": acc_id, "weight": weight})
+            total_weight += weight
 
-    # Rule R-L4: nobody to share with, the loss stays as bad debt
-    if not weights:
+    if not eligible_accounts:
+        # R-L4: Bad Debt
         reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
         return reports
 
-    total = sum(weights.values())
-    shares = {acc_id: remaining * w // total for acc_id, w in weights.items()}
-    leftover = remaining - sum(shares.values())
-    ranked = sorted(weights, key=lambda a: (-weights[a], a))
-    for acc_id in ranked[:leftover]:
-        shares[acc_id] += 1
+    # Calculate shares
+    shares = {}
+    sum_base = 0
+    for item in eligible_accounts:
+        base = (remaining * item["weight"]) // total_weight
+        shares[item["id"]] = base
+        sum_base += base
 
-    for acc_id in sorted(shares):
+    leftover = remaining - sum_base
+
+    # Sort for leftover distribution: descending weight, then ascending account id
+    # Note: Python sort is stable.
+    # To sort by weight desc, then id asc:
+    # Sort by id asc first, then by weight desc.
+    sorted_for_leftover = sorted(eligible_accounts, key=lambda x: x["id"])
+    sorted_for_leftover.sort(key=lambda x: x["weight"], reverse=True)
+
+    for i in range(leftover):
+        target_id = sorted_for_leftover[i]["id"]
+        shares[target_id] += 1
+
+    # Apply shares
+    for acc_id, share in shares.items():
+        if share > 0:
+            state.accounts[acc_id].free_cash -= share
+
+    x_acc.free_cash += remaining
+
+    # R-L5: Report ADL_APPLIED in ascending account-id order
+    adl_reports = []
+    for acc_id in sorted(shares.keys()):
         if shares[acc_id] > 0:
-            state.accounts[acc_id].free_cash -= shares[acc_id]
-            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
-    victim.free_cash += remaining
+            adl_reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
+
+    reports.extend(adl_reports)
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
    x_acc = state.accounts[account_id]
    deficit = max(0, -x_acc.free_cash)

    if deficit == 0:
        return []

    reports = []

    # R-L2: Insurance Draw
    cover = min(deficit, max(0, state.fee_vault))
    if cover > 0:
        state.fee_vault -= cover
        x_acc.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))

    remaining = deficit - cover
    if remaining == 0:
        return reports

    # R-L3: Loss Sharing
    eligible_accounts = []
    total_weight = 0
    for acc_id, acc in state.accounts.items():
        if acc_id == "LIQ" or acc_id == account_id:
            continue
        if acc.position != 0 and (acc.position > 0) != (pre_position > 0):
            weight = abs(acc.position)
            eligible_accounts.append({"id": acc_id, "weight": weight})
            total_weight += weight

    if not eligible_accounts:
        # R-L4: Bad Debt
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    # Calculate shares
    shares = {}
    sum_base = 0
    for item in eligible_accounts:
        base = (remaining * item["weight"]) // total_weight
        shares[item["id"]] = base
        sum_base += base

    leftover = remaining - sum_base

    # Sort for leftover distribution: descending weight, then ascending account id
    # Note: Python sort is stable.
    # To sort by weight desc, then id asc:
    # Sort by id asc first, then by weight desc.
    sorted_for_leftover = sorted(eligible_accounts, key=lambda x: x["id"])
    sorted_for_leftover.sort(key=lambda x: x["weight"], reverse=True)

    for i in range(leftover):
        target_id = sorted_for_leftover[i]["id"]
        shares[target_id] += 1

    # Apply shares
    for acc_id, share in shares.items():
        if share > 0:
            state.accounts[acc_id].free_cash -= share

    x_acc.free_cash += remaining

    # R-L5: Report ADL_APPLIED in ascending account-id order
    adl_reports = []
    for acc_id in sorted(shares.keys()):
        if shares[acc_id] > 0:
            adl_reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))

    reports.extend(adl_reports)
    return reports
```
````
