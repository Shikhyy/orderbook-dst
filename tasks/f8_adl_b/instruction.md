# Task f8_adl_b: Bankruptcy Procedure (Insurance Draw and Loss Sharing)

## 1. Goal
Implement the bankruptcy procedure:
```python
def handle_bankruptcy(engine: Any, account_id: str, pre_position: int) -> list[Report]:
```
in `exchange_core/handlers/bankruptcy.py`.

A liquidation can leave an account with negative cash. The procedure covers that deficit first from the fee vault and then by sharing the rest among the accounts on the other side of the liquidated position. It changes the state in place and returns its reports.

The public tests for this task are shown in full in the "Public Tests (Visible)" section of the prompt.

## 2. Interface

```python
from exchange_core.types import Report

def handle_bankruptcy(engine: "Engine", account_id: str, pre_position: int) -> list[Report]:
    """Cover the deficit of a just-liquidated account and return the reports in order."""
```

### How the procedure is called (this part already exists, you do not write it)

A `PRICE_CRASH` event carries a `mark_price`. The engine handles it exactly like a `PRICE_SHOCK` event (the margin waterfall: it sets the mark price, examines the accounts except `LIQ` in ascending account-id order, cancels resting orders of an account in breach and, if it is still in breach, liquidates its whole position against `LIQ` at the mark price). The only difference: right after each `LIQUIDATED` report, the engine calls `handle_bankruptcy(engine, account_id, pre_position)` for the liquidated account and appends the returned reports directly after that `LIQUIDATED` report, before it examines the next account. `pre_position` is the signed position of the account before the liquidation (the `qty` of the `LIQUIDATED` report). The engine reads the live state, so the cash that your procedure takes from an account counts when that account is examined later in the same event. An account that was already examined is not examined again. `PRICE_SHOCK` never calls the procedure.

When your procedure is called, the liquidated account has `position == 0` and no resting order. The procedure does not examine, cancel or liquidate any account: it only does what the rules below say.

### The `engine` argument

`engine` is the exchange `Engine` object. The procedure may use this member:

- `engine.state`: the `EngineState` instance, described in the `exchange_core/state.py` context file below. The procedure reads it and changes it in place. `engine.state.accounts` maps each account id to an `Account` (`free_cash`, `locked_margin`, `position`, `volume`). `engine.state.fee_vault` is the fee vault.

The `Engine` class itself is not part of this task. Use only the member listed here; no other attribute of `engine` is available.

## 3. Rules

**R-L1.** The deficit of the liquidated account X is `max(0, -free_cash)` of X at the moment the procedure is called. If the deficit is 0, nothing changes and the procedure returns no report.

**R-L2.** The fee vault pays first. `cover = min(deficit, max(0, fee_vault))`. If `cover > 0`: `fee_vault` decreases by `cover`, `free_cash` of X increases by `cover`, and the procedure reports `Report(kind="INSURANCE_DRAWN", account=X, qty=cover)`. The rest is `remaining = deficit - cover`. If `remaining == 0`, the procedure ends.

**R-L3.** The rest is shared by the accounts on the other side of the liquidated position. An account is **eligible** when it is neither `LIQ` nor X, its position is not 0, and its position has the opposite sign to `pre_position`. The weight of an eligible account is `abs(position)`. Let `total` be the sum of all weights. Each eligible account first gets `base = remaining * weight // total` (floor division). The units that remain, `leftover = remaining - sum(base)`, are always fewer than the number of eligible accounts. Sort the eligible accounts by descending weight; accounts with the same weight are sorted by ascending account id (string order: `"A10"` comes before `"A2"`). Each of the first `leftover` accounts in this order gets one more unit. The result is the `share` of each eligible account.
- Each eligible account pays its `share` from `free_cash`. The cash can become negative; nothing else is done for that account (no cancel, no liquidation, no check).
- `free_cash` of X increases by `remaining`.
- For each eligible account with `share > 0`, in ascending account-id order (string order), the procedure reports `Report(kind="ADL_APPLIED", account=<that account>, qty=share)`.

**R-L4.** If `remaining > 0` and no account is eligible, nothing else changes: X keeps its negative cash and the procedure reports `Report(kind="BAD_DEBT", account=X, qty=remaining)`.

**R-L5.** The reports of the procedure are, in this order: `INSURANCE_DRAWN` (if any), then all the `ADL_APPLIED` reports, or `BAD_DEBT`; never both. Total cash plus `fee_vault` is unchanged by the procedure. Positions, locks and volumes do not change.

## 4. Allowed imports

You may import standard library modules and the following `exchange_core` modules only:
- `exchange_core.types`
- `exchange_core.state`
- `exchange_core.intmath`
- `exchange_core.config`
- `exchange_core.book`
- `exchange_core.ledger`
- `exchange_core.engine`

All other `exchange_core` imports (including `exchange_core.rules.*` and other handlers such as `exchange_core.handlers.shock` or `exchange_core.handlers.crash`) are forbidden. Dynamic import calls (`importlib`, `__import__`, `eval`, `exec`) are strictly forbidden. Any violation immediately fails grading with `FORBIDDEN_IMPORT` and a score of 0.

## 5. Output format

Provide the complete contents of `exchange_core/handlers/bankruptcy.py` in exactly this layout, with the `### FILE:` line above one markdown code block:

### FILE: exchange_core/handlers/bankruptcy.py
```python
# complete file contents here
```
