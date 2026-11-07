# ministral_8b · f8_adl_b · trial 0 — failure (lowest score)

| Field | Value |
|---|---|
| Model ID (requested / served) | `ministral-8b-latest` / `ministral-8b-latest` |
| Settings | `{"max_tokens": 8000, "base_url": "https://api.mistral.ai/v1", "api_key_env": "MISTRAL_API_KEY"}` |
| Mode | single_turn |
| Score (T1 / T2 / T3) | 0.1833 (0.6666666666666666 / 0.16666666666666666 / 0.0) |
| Outcome | D1 |
| Error | – |
| Tokens in / out | 7038 / 729 |
| Latency (s) | 11.152415037155151 |
| Stop reason | stop |
| Timestamp | 2026-11-05T14:50:53.215527+00:00 |
| Prompt | [`prompt.txt`](../../results/main/raw/ministral_8b/f8_adl_b/0/prompt.txt) (sha256 `ac94d0d4f5f24be0…`) |
| Raw files | [`results/main/raw/ministral_8b/f8_adl_b/0/`](../../results/main/raw/ministral_8b/f8_adl_b/0) |

## First failure (hidden trace)

- Seed 11000, event 23: **D1** — Report mismatch
- Message: `event 23 report differs from reference`

```json
{
  "expected": [
    {
      "kind": "MARK_SET",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 0,
      "taker_order_id": 0,
      "account": "",
      "mark_price": 246330826,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "LIQUIDATED",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": -4,
      "taker_order_id": 0,
      "account": "A10",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "LIQUIDATED",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": -7,
      "taker_order_id": 0,
      "account": "A11",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "INSURANCE_DRAWN",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 4998650,
      "taker_order_id": 0,
      "account": "A11",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "ADL_APPLIED",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 52449032,
      "taker_order_id": 0,
      "account": "A1",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "ADL_APPLIED",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 183571614,
      "taker_order_id": 0,
      "account": "A12",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "ADL_APPLIED",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 78673548,
      "taker_order_id": 0,
      "account": "A2",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "ADL_APPLIED",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 104898065,
      "taker_order_id": 0,
      "account": "A3",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "CANCELLED",
      "order_id": 13,
      "reason": "RISK",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 0,
      "taker_order_id": 0,
      "account": "",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "CANCELLED",
      "order_id": 14,
      "reason": "RISK",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 0,
      "taker_order_id": 0,
      "account": "",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "LIQUIDATED",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": -5,
      "taker_order_id": 0,
      "account": "A13",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "ADL_APPLIED",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 16459896,
      "taker_order_id": 0,
      "account": "A1",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "ADL_APPLIED",
      "order_id": 0,
      "reason": "",
      "buy_order_id": 0,
      "sell_order_id": 0,
      "price": 0,
      "qty": 57609636,
      "taker_order_id": 0,
      "account": "A12",
      "mark_price": 0,
      "bps": 0,
      "session": "",
      "leg_index": 0
    },
    {
      "kind": "ADL_APPLI
... (truncated; full diff in score.json)
```

## Labels on all failing hidden seeds

D1×11, I1×20 (over 20 failing seeds of 20)

## Diff against the reference solution

Differences are not errors by themselves (many correct solutions differ from the reference); use this to find the line that breaks the first failure above.

```diff
--- reference/f8_adl_b/bankruptcy.py
+++ model/exchange_core/handlers/bankruptcy.py
@@ -1,56 +1,84 @@
 """exchange_core/handlers/bankruptcy.py
-Bankruptcy procedure run after a liquidation: insurance draw, then pro-rata loss sharing.
-Rules R-L1 to R-L4. Reference only.
+Bankruptcy procedure after a liquidation: insurance draw, then loss sharing.
+Rules R-L1 to R-L5. Target for task f8_adl_b.
 """
 from exchange_core.types import Report
+from exchange_core.state import EngineState
+from exchange_core.ledger import get_account, transfer_cash
+from exchange_core.intmath import round_half_even
 
+def handle_bankruptcy(engine: "Engine", account_id: str, pre_position: int) -> list[Report]:
+    """Cover the deficit of a just-liquidated account and return the reports in order."""
+    state: EngineState = engine.state
+    reports = []
 
-def handle_bankruptcy(engine: "Engine", account_id: str, pre_position: int) -> list[Report]:  # type: ignore # noqa: F821
-    """Cover the negative cash of a just-liquidated account and return the reports."""
-    state = engine.state
-    victim = state.accounts[account_id]
+    # R-L1: Calculate deficit
+    account = get_account(state, account_id)
+    if account is None:
+        return reports
 
-    # Rule R-L1: the deficit is the negative cash that remains after liquidation
-    deficit = max(0, -victim.free_cash)
+    deficit = max(0, -account.free_cash)
     if deficit == 0:
-        return []
+        return reports
 
-    reports: list[Report] = []
-
-    # Rule R-L2: the fee vault (never below zero) pays first
+    # R-L2: Cover from fee vault
     cover = min(deficit, max(0, state.fee_vault))
     if cover > 0:
         state.fee_vault -= cover
-        victim.free_cash += cover
+        account.free_cash += cover
         reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
+        remaining = deficit - cover
+    else:
+        remaining = deficit
 
-    remaining = deficit - cover
     if remaining == 0:
         return reports
 
-    # Rule R-L3: the rest is shared by the accounts on the other side of the liquidated position
-    weights: dict[str, int] = {}
+    # R-L3: Find eligible accounts and calculate shares
+    eligible_accounts = []
+    total_weight = 0
+
     for acc_id, acc in state.accounts.items():
-        if acc_id == "LIQ" or acc_id == account_id or acc.position == 0:
+        if acc_id == account_id or acc_id == "LIQ":
             continue
-        if (acc.position > 0) != (pre_position > 0):
-            weights[acc_id] = abs(acc.position)
+        if acc.position == 0:
+            continue
+        if (acc.position > 0 and pre_position > 0) or (acc.position < 0 and pre_position < 0):
+            continue
 
-    # Rule R-L4: nobody to share with, the loss stays as bad debt
-    if not weights:
+        eligible_accounts.append((acc_id, abs(acc.position)))
+        total_weight += abs(acc.position)
+
+    if total_weight == 0:
+        # R-L4: No eligible accounts
         reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
         return reports
 
-    total = sum(weights.values())
-    shares = {acc_id: remaining * w // total for acc_id, w in weights.items()}
-    leftover = remaining - sum(shares.values())
-    ranked = sorted(weights, key=lambda a: (-weights[a], a))
-    for acc_id in ranked[:leftover]:
-        shares[acc_id] += 1
+    # Sort eligible accounts by descending weight, then ascending account_id
+    eligible_accounts.sort(key=lambda x: (-x[1], x[0]))
 
-    for acc_id in sorted(shares):
-        if shares[acc_id] > 0:
-            state.accounts[acc_id].free_cash -= shares[acc_id]
-            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
-    victim.free_cash += remaining
+    # Calculate base shares
+    base_shares = []
+    for acc_id, weight in eligible_accounts:
+        base = remaining * weight // total_weight
+        base_shares.append((acc_id, base))
+
+    # Calculate leftover shares
+    sum_base = sum(base for _, base in base_shares)
+    leftover = remaining - sum_base
+
+    # Distribute leftover shares
+    for i in range(leftover):
+        acc_id, _ = eligible_accounts[i]
+        base_shares[i] = (acc_id, base_shares[i][1] + 1)
+
+    # Transfer cash and create reports
+    for acc_id, share in base_shares:
+        if share > 0:
+            transfer_cash(state, acc_id, account_id, share)
+            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))
+
+    # Add remaining to account
+    account.free_cash += remaining
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
from exchange_core.state import EngineState
from exchange_core.ledger import get_account, transfer_cash
from exchange_core.intmath import round_half_even

def handle_bankruptcy(engine: "Engine", account_id: str, pre_position: int) -> list[Report]:
    """Cover the deficit of a just-liquidated account and return the reports in order."""
    state: EngineState = engine.state
    reports = []

    # R-L1: Calculate deficit
    account = get_account(state, account_id)
    if account is None:
        return reports

    deficit = max(0, -account.free_cash)
    if deficit == 0:
        return reports

    # R-L2: Cover from fee vault
    cover = min(deficit, max(0, state.fee_vault))
    if cover > 0:
        state.fee_vault -= cover
        account.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
        remaining = deficit - cover
    else:
        remaining = deficit

    if remaining == 0:
        return reports

    # R-L3: Find eligible accounts and calculate shares
    eligible_accounts = []
    total_weight = 0

    for acc_id, acc in state.accounts.items():
        if acc_id == account_id or acc_id == "LIQ":
            continue
        if acc.position == 0:
            continue
        if (acc.position > 0 and pre_position > 0) or (acc.position < 0 and pre_position < 0):
            continue

        eligible_accounts.append((acc_id, abs(acc.position)))
        total_weight += abs(acc.position)

    if total_weight == 0:
        # R-L4: No eligible accounts
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    # Sort eligible accounts by descending weight, then ascending account_id
    eligible_accounts.sort(key=lambda x: (-x[1], x[0]))

    # Calculate base shares
    base_shares = []
    for acc_id, weight in eligible_accounts:
        base = remaining * weight // total_weight
        base_shares.append((acc_id, base))

    # Calculate leftover shares
    sum_base = sum(base for _, base in base_shares)
    leftover = remaining - sum_base

    # Distribute leftover shares
    for i in range(leftover):
        acc_id, _ = eligible_accounts[i]
        base_shares[i] = (acc_id, base_shares[i][1] + 1)

    # Transfer cash and create reports
    for acc_id, share in base_shares:
        if share > 0:
            transfer_cash(state, acc_id, account_id, share)
            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))

    # Add remaining to account
    account.free_cash += remaining

    return reports
```
````
