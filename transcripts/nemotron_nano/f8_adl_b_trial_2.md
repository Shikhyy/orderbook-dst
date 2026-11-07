# nemotron_nano · f8_adl_b · trial 2 — pass

| Field | Value |
|---|---|
| Model ID (requested / served) | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` / `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |
| Settings | `{"max_tokens": 16000, "base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 1.0 (1.0 / 1.0 / 1.0) |
| Outcome | pass |
| Error | – |
| Tokens in / out | 7049 / 9880 |
| Latency (s) | 91.2441201210022 |
| Stop reason | stop |
| Timestamp | 2026-11-05T14:50:41.340576+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/nemotron_nano/f8_adl_b/2/prompt.txt) (sha256 `ac94d0d4f5f24be0…`) |
| Raw files | [`results/main/raw/nemotron_nano/f8_adl_b/2/`](../../results/main/raw/nemotron_nano/f8_adl_b/2) |

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f8_adl_b/bankruptcy.py
+++ model/exchange_core/handlers/bankruptcy.py
@@ -1,56 +1,86 @@
 """exchange_core/handlers/bankruptcy.py
-Bankruptcy procedure run after a liquidation: insurance draw, then pro-rata loss sharing.
-Rules R-L1 to R-L4. Reference only.
+Bankruptcy procedure after a liquidation: insurance draw, then loss sharing.
+Rules R-L1 to R-L5. Target for task f8_adl_b.
 """
 from exchange_core.types import Report
 
 
-def handle_bankruptcy(engine: "Engine", account_id: str, pre_position: int) -> list[Report]:  # type: ignore # noqa: F821
-    """Cover the negative cash of a just-liquidated account and return the reports."""
-    state = engine.state
-    victim = state.accounts[account_id]
-
-    # Rule R-L1: the deficit is the negative cash that remains after liquidation
-    deficit = max(0, -victim.free_cash)
+def handle_bankruptcy(
+    engine: "Engine", account_id: str, pre_position: int  # type: ignore # noqa: F821
+) -> list[Report]:
+    """Cover the deficit of a just-liquidated account and return the reports in order."""
+    # 1. compute deficit
+    acc = engine.state.accounts[account_id]
+    deficit = -acc.free_cash if acc.free_cash < 0 else 0
     if deficit == 0:
         return []
 
-    reports: list[Report] = []
-
-    # Rule R-L2: the fee vault (never below zero) pays first
-    cover = min(deficit, max(0, state.fee_vault))
+    # 2. insurance draw from fee vault
+    fee_vault = engine.state.fee_vault
+    cover = min(deficit, max(0, fee_vault))
+    reports = []
     if cover > 0:
-        state.fee_vault -= cover
-        victim.free_cash += cover
+        engine.state.fee_vault -= cover
+        acc.free_cash += cover
         reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
 
     remaining = deficit - cover
     if remaining == 0:
         return reports
 
-    # Rule R-L3: the rest is shared by the accounts on the other side of the liquidated position
-    weights: dict[str, int] = {}
-    for acc_id, acc in state.accounts.items():
-        if acc_id == "LIQ" or acc_id == account_id or acc.position == 0:
+    # 3. find eligible accounts
+    eligible = []  # (account_id, weight)
+    for a_id, a in engine.state.accounts.items():
+        if a_id == account_id or a_id == "LIQ":
             continue
-        if (acc.position > 0) != (pre_position > 0):
-            weights[acc_id] = abs(acc.position)
+        if a.position == 0:
+            continue
+        # opposite sign to pre_position
+        if pre_position > 0 and a.position < 0:
+            eligible.append((a_id, abs(a.position)))
+        elif pre_position < 0 and a.position > 0:
+            eligible.append((a_id, abs(a.position)))
 
-    # Rule R-L4: nobody to share with, the loss stays as bad debt
-    if not weights:
+    total_weight = sum(w for _, w in eligible)
+    if total_weight == 0:
+        # no eligible accounts => bad debt
         reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
         return reports
 
-    total = sum(weights.values())
-    shares = {acc_id: remaining * w // total for acc_id, w in weights.items()}
-    leftover = remaining - sum(shares.values())
-    ranked = sorted(weights, key=lambda a: (-weights[a], a))
-    for acc_id in ranked[:leftover]:
-        shares[acc_id] += 1
+    # 4. compute base shares
+    base_shares = {}
+    sum_base = 0
+    for a_id, w in eligible:
+        base = remaining * w // total_weight
+        base_shares[a_id] = base
+        sum_base += base
 
-    for acc_id in sorted(shares):
-        if shares[acc_id] > 0:
-            state.accounts[acc_id].free_cash -= shares[acc_id]
-            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
-    victim.free_cash += remaining
+    leftover = remaining - sum_base  # 0 <= leftover < len(eligible)
+
+    # 5. sort eligible by descending weight, then ascending account_id
+    eligible_with_base = [(a_id, w, base_shares[a_id]) for a_id, w in eligible]
+    eligible_with_base.sort(key=lambda x: (-x[1], x[0]))  # weight desc, id asc
+
+    # allocate extra 1 to first leftover accounts
+    for i in range(leftover):
+        a_id, w, base = eligible_with_base[i]
+        eligible_with_base[i] = (a_id, w, base + 1)
+
+    # 6. report ADL_APPLIED in ascending account_id order
+    share_dict = {}
+    for a_id, w, base in eligible_with_base:
+        share = base
+        if share > 0:
+            # deduct from free_cash
+            a = engine.state.accounts[a_id]
+            a.free_cash -= share
+            share_dict[a_id] = share
+
+    # sort by account_id ascending for reporting order
+    for a_id, share in sorted(share_dict.items(), key=lambda x: x[0]):
+        reports.append(Report(kind="ADL_APPLIED", account=a_id, qty=share))
+
+    # 7. increase free_cash of the liquidated account by remaining
+    acc.free_cash += remaining
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
    # 1. compute deficit
    acc = engine.state.accounts[account_id]
    deficit = -acc.free_cash if acc.free_cash < 0 else 0
    if deficit == 0:
        return []

    # 2. insurance draw from fee vault
    fee_vault = engine.state.fee_vault
    cover = min(deficit, max(0, fee_vault))
    reports = []
    if cover > 0:
        engine.state.fee_vault -= cover
        acc.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))

    remaining = deficit - cover
    if remaining == 0:
        return reports

    # 3. find eligible accounts
    eligible = []  # (account_id, weight)
    for a_id, a in engine.state.accounts.items():
        if a_id == account_id or a_id == "LIQ":
            continue
        if a.position == 0:
            continue
        # opposite sign to pre_position
        if pre_position > 0 and a.position < 0:
            eligible.append((a_id, abs(a.position)))
        elif pre_position < 0 and a.position > 0:
            eligible.append((a_id, abs(a.position)))

    total_weight = sum(w for _, w in eligible)
    if total_weight == 0:
        # no eligible accounts => bad debt
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    # 4. compute base shares
    base_shares = {}
    sum_base = 0
    for a_id, w in eligible:
        base = remaining * w // total_weight
        base_shares[a_id] = base
        sum_base += base

    leftover = remaining - sum_base  # 0 <= leftover < len(eligible)

    # 5. sort eligible by descending weight, then ascending account_id
    eligible_with_base = [(a_id, w, base_shares[a_id]) for a_id, w in eligible]
    eligible_with_base.sort(key=lambda x: (-x[1], x[0]))  # weight desc, id asc

    # allocate extra 1 to first leftover accounts
    for i in range(leftover):
        a_id, w, base = eligible_with_base[i]
        eligible_with_base[i] = (a_id, w, base + 1)

    # 6. report ADL_APPLIED in ascending account_id order
    share_dict = {}
    for a_id, w, base in eligible_with_base:
        share = base
        if share > 0:
            # deduct from free_cash
            a = engine.state.accounts[a_id]
            a.free_cash -= share
            share_dict[a_id] = share

    # sort by account_id ascending for reporting order
    for a_id, share in sorted(share_dict.items(), key=lambda x: x[0]):
        reports.append(Report(kind="ADL_APPLIED", account=a_id, qty=share))

    # 7. increase free_cash of the liquidated account by remaining
    acc.free_cash += remaining

    return reports
```
````
