# nemotron_ultra · f8_adl_b · trial 0 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `nvidia/nemotron-3-ultra-550b-a55b:free` / `nvidia/nemotron-3-ultra-550b-a55b:free` |
| Settings | `{"max_tokens": 16000, "base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 7049 / 2052 |
| Latency (s) | 39.30720806121826 |
| Stop reason | stop |
| Timestamp | 2026-11-05T14:32:29.768855+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/nemotron_ultra/f8_adl_b/0/prompt.txt) (sha256 `ac94d0d4f5f24be0…`) |
| Raw files | [`results/main/raw/nemotron_ultra/f8_adl_b/0/`](../../results/main/raw/nemotron_ultra/f8_adl_b/0) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f8_adl_b/bankruptcy.py
+++ model/exchange_core/handlers/bankruptcy.py
@@ -1,56 +1,90 @@
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
-
-    # Rule R-L1: the deficit is the negative cash that remains after liquidation
-    deficit = max(0, -victim.free_cash)
-    if deficit == 0:
-        return []
-
     reports: list[Report] = []
 
-    # Rule R-L2: the fee vault (never below zero) pays first
+    # R-L1: Calculate deficit
+    account = state.accounts[account_id]
+    deficit = max(0, -account.free_cash)
+    if deficit == 0:
+        return reports
+
+    # R-L2: Fee vault pays first
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
+    # R-L3: Find eligible accounts on the other side
+    # Eligible: not LIQ, not X, position != 0, sign(position) opposite to sign(pre_position)
+    eligible: list[tuple[str, int]] = []  # (account_id, weight)
+    pre_sign = 1 if pre_position > 0 else -1 if pre_position < 0 else 0
+
     for acc_id, acc in state.accounts.items():
-        if acc_id == "LIQ" or acc_id == account_id or acc.position == 0:
+        if acc_id == "LIQ" or acc_id == account_id:
             continue
-        if (acc.position > 0) != (pre_position > 0):
-            weights[acc_id] = abs(acc.position)
+        pos = acc.position
+        if pos == 0:
+            continue
+        pos_sign = 1 if pos > 0 else -1
+        if pos_sign != -pre_sign:  # opposite sign
+            continue
+        weight = abs(pos)
+        eligible.append((acc_id, weight))
 
-    # Rule R-L4: nobody to share with, the loss stays as bad debt
-    if not weights:
+    if not eligible:
+        # R-L4: No eligible accounts, bad debt
         reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
         return reports
 
-    total = sum(weights.values())
-    shares = {acc_id: remaining * w // total for acc_id, w in weights.items()}
-    leftover = remaining - sum(shares.values())
-    ranked = sorted(weights, key=lambda a: (-weights[a], a))
-    for acc_id in ranked[:leftover]:
-        shares[acc_id] += 1
+    # Calculate base shares
+    total_weight = sum(w for _, w in eligible)
+    base_shares: dict[str, int] = {}
+    sum_base = 0
+    for acc_id, weight in eligible:
+        base = remaining * weight // total_weight
+        base_shares[acc_id] = base
+        sum_base += base
 
-    for acc_id in sorted(shares):
-        if shares[acc_id] > 0:
-            state.accounts[acc_id].free_cash -= shares[acc_id]
-            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
-    victim.free_cash += remaining
+    leftover = remaining - sum_base
+
+    # Sort eligible by descending weight, then ascending account_id
+    eligible_sorted = sorted(eligible, key=lambda x: (-x[1], x[0]))
+
+    # First `leftover` accounts get +1
+    final_shares: dict[str, int] = {}
+    for i, (acc_id, _) in enumerate(eligible_sorted):
+        share = base_shares[acc_id]
+        if i < leftover:
+            share += 1
+        final_shares[acc_id] = share
+
+    # Apply shares: each eligible account pays from free_cash
+    for acc_id, share in final_shares.items():
+        if share > 0:
+            state.accounts[acc_id].free_cash -= share
+
+    # X's free_cash increases by remaining
+    account.free_cash += remaining
+
+    # Report ADL_APPLIED in ascending account_id order for accounts with share > 0
+    for acc_id in sorted(final_shares.keys()):
+        share = final_shares[acc_id]
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


def handle_bankruptcy(
    engine: "Engine", account_id: str, pre_position: int  # type: ignore # noqa: F821
) -> list[Report]:
    """Cover the deficit of a just-liquidated account and return the reports in order."""
    state = engine.state
    reports: list[Report] = []

    # R-L1: Calculate deficit
    account = state.accounts[account_id]
    deficit = max(0, -account.free_cash)
    if deficit == 0:
        return reports

    # R-L2: Fee vault pays first
    cover = min(deficit, max(0, state.fee_vault))
    if cover > 0:
        state.fee_vault -= cover
        account.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))

    remaining = deficit - cover
    if remaining == 0:
        return reports

    # R-L3: Find eligible accounts on the other side
    # Eligible: not LIQ, not X, position != 0, sign(position) opposite to sign(pre_position)
    eligible: list[tuple[str, int]] = []  # (account_id, weight)
    pre_sign = 1 if pre_position > 0 else -1 if pre_position < 0 else 0

    for acc_id, acc in state.accounts.items():
        if acc_id == "LIQ" or acc_id == account_id:
            continue
        pos = acc.position
        if pos == 0:
            continue
        pos_sign = 1 if pos > 0 else -1
        if pos_sign != -pre_sign:  # opposite sign
            continue
        weight = abs(pos)
        eligible.append((acc_id, weight))

    if not eligible:
        # R-L4: No eligible accounts, bad debt
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    # Calculate base shares
    total_weight = sum(w for _, w in eligible)
    base_shares: dict[str, int] = {}
    sum_base = 0
    for acc_id, weight in eligible:
        base = remaining * weight // total_weight
        base_shares[acc_id] = base
        sum_base += base

    leftover = remaining - sum_base

    # Sort eligible by descending weight, then ascending account_id
    eligible_sorted = sorted(eligible, key=lambda x: (-x[1], x[0]))

    # First `leftover` accounts get +1
    final_shares: dict[str, int] = {}
    for i, (acc_id, _) in enumerate(eligible_sorted):
        share = base_shares[acc_id]
        if i < leftover:
            share += 1
        final_shares[acc_id] = share

    # Apply shares: each eligible account pays from free_cash
    for acc_id, share in final_shares.items():
        if share > 0:
            state.accounts[acc_id].free_cash -= share

    # X's free_cash increases by remaining
    account.free_cash += remaining

    # Report ADL_APPLIED in ascending account_id order for accounts with share > 0
    for acc_id in sorted(final_shares.keys()):
        share = final_shares[acc_id]
        if share > 0:
            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))

    return reports
```
````
