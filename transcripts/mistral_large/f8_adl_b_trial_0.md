# mistral_large · f8_adl_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `mistral-large-4` / `mistral-large-4` |
| Settings | `{"max_tokens": 16000, "base_url": "https://api.mistral.ai/v1", "api_key_env": "MISTRAL_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 6774 / 4666 |
| Latency (s) | 38.21784281730652 |
| Stop reason | stop |
| Timestamp | 2026-11-05T14:35:10.367617+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/mistral_large/f8_adl_b/0/prompt.txt) (sha256 `ac94d0d4f5f24be0…`) |
| Raw files | [`results/main/raw/mistral_large/f8_adl_b/0/`](../../results/main/raw/mistral_large/f8_adl_b/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f8_adl_b/bankruptcy.py
+++ model/exchange_core/handlers/bankruptcy.py
@@ -1,56 +1,70 @@
 """exchange_core/handlers/bankruptcy.py
-Bankruptcy procedure run after a liquidation: insurance draw, then pro-rata loss sharing.
-Rules R-L1 to R-L4. Reference only.
+Bankruptcy procedure after a liquidation: insurance draw, then loss sharing.
+Rules R-L1 to R-L5. Target for task f8_adl_b.
 """
 from exchange_core.types import Report
 
+LIQ_ACCOUNT = "LIQ"
 
-def handle_bankruptcy(engine: "Engine", account_id: str, pre_position: int) -> list[Report]:  # type: ignore # noqa: F821
-    """Cover the negative cash of a just-liquidated account and return the reports."""
+
+def handle_bankruptcy(
+    engine: "Engine", account_id: str, pre_position: int  # type: ignore # noqa: F821
+) -> list[Report]:
+    """Cover the deficit of a just-liquidated account and return the reports in order."""
     state = engine.state
-    victim = state.accounts[account_id]
-
-    # Rule R-L1: the deficit is the negative cash that remains after liquidation
-    deficit = max(0, -victim.free_cash)
-    if deficit == 0:
-        return []
-
+    account = state.accounts[account_id]
     reports: list[Report] = []
 
-    # Rule R-L2: the fee vault (never below zero) pays first
+    # R-L1: the deficit is max(0, -free_cash) of the liquidated account X.
+    deficit = max(0, -account.free_cash)
+    if deficit == 0:
+        return reports
+
+    # R-L2: the fee vault pays first.
     cover = min(deficit, max(0, state.fee_vault))
     if cover > 0:
         state.fee_vault -= cover
-        victim.free_cash += cover
+        account.free_cash += cover
         reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
 
     remaining = deficit - cover
     if remaining == 0:
         return reports
 
-    # Rule R-L3: the rest is shared by the accounts on the other side of the liquidated position
-    weights: dict[str, int] = {}
+    # R-L3: the rest is shared by the accounts on the other side of the position.
+    eligible: list[tuple[str, int]] = []  # (account_id, weight = abs(position))
     for acc_id, acc in state.accounts.items():
-        if acc_id == "LIQ" or acc_id == account_id or acc.position == 0:
+        if acc_id == LIQ_ACCOUNT or acc_id == account_id:
             continue
-        if (acc.position > 0) != (pre_position > 0):
-            weights[acc_id] = abs(acc.position)
+        if acc.position == 0:
+            continue
+        if acc.position * pre_position >= 0:
+            continue  # same sign as pre_position (or pre_position == 0)
+        eligible.append((acc_id, abs(acc.position)))
 
-    # Rule R-L4: nobody to share with, the loss stays as bad debt
-    if not weights:
+    # R-L4: nobody on the other side can share -> bad debt.
+    if not eligible:
         reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
         return reports
 
-    total = sum(weights.values())
-    shares = {acc_id: remaining * w // total for acc_id, w in weights.items()}
+    total = sum(weight for _, weight in eligible)
+    shares = {acc_id: remaining * weight // total for acc_id, weight in eligible}
     leftover = remaining - sum(shares.values())
-    ranked = sorted(weights, key=lambda a: (-weights[a], a))
-    for acc_id in ranked[:leftover]:
-        shares[acc_id] += 1
 
+    # Distribute the leftover units: descending weight, ties by ascending account id.
+    by_weight = sorted(eligible, key=lambda item: (-item[1], item[0]))
+    for i in range(leftover):
+        shares[by_weight[i][0]] += 1
+
+    # Each eligible account pays its share (cash may become negative); X receives the rest.
+    for acc_id, share in shares.items():
+        state.accounts[acc_id].free_cash -= share
+    account.free_cash += remaining
+
+    # R-L5: ADL_APPLIED reports in ascending account-id order, only for positive shares.
     for acc_id in sorted(shares):
-        if shares[acc_id] > 0:
-            state.accounts[acc_id].free_cash -= shares[acc_id]
-            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
-    victim.free_cash += remaining
+        share = shares[acc_id]
+        if share > 0:
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

LIQ_ACCOUNT = "LIQ"


def handle_bankruptcy(
    engine: "Engine", account_id: str, pre_position: int  # type: ignore # noqa: F821
) -> list[Report]:
    """Cover the deficit of a just-liquidated account and return the reports in order."""
    state = engine.state
    account = state.accounts[account_id]
    reports: list[Report] = []

    # R-L1: the deficit is max(0, -free_cash) of the liquidated account X.
    deficit = max(0, -account.free_cash)
    if deficit == 0:
        return reports

    # R-L2: the fee vault pays first.
    cover = min(deficit, max(0, state.fee_vault))
    if cover > 0:
        state.fee_vault -= cover
        account.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))

    remaining = deficit - cover
    if remaining == 0:
        return reports

    # R-L3: the rest is shared by the accounts on the other side of the position.
    eligible: list[tuple[str, int]] = []  # (account_id, weight = abs(position))
    for acc_id, acc in state.accounts.items():
        if acc_id == LIQ_ACCOUNT or acc_id == account_id:
            continue
        if acc.position == 0:
            continue
        if acc.position * pre_position >= 0:
            continue  # same sign as pre_position (or pre_position == 0)
        eligible.append((acc_id, abs(acc.position)))

    # R-L4: nobody on the other side can share -> bad debt.
    if not eligible:
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    total = sum(weight for _, weight in eligible)
    shares = {acc_id: remaining * weight // total for acc_id, weight in eligible}
    leftover = remaining - sum(shares.values())

    # Distribute the leftover units: descending weight, ties by ascending account id.
    by_weight = sorted(eligible, key=lambda item: (-item[1], item[0]))
    for i in range(leftover):
        shares[by_weight[i][0]] += 1

    # Each eligible account pays its share (cash may become negative); X receives the rest.
    for acc_id, share in shares.items():
        state.accounts[acc_id].free_cash -= share
    account.free_cash += remaining

    # R-L5: ADL_APPLIED reports in ascending account-id order, only for positive shares.
    for acc_id in sorted(shares):
        share = shares[acc_id]
        if share > 0:
            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))

    return reports
```
````
