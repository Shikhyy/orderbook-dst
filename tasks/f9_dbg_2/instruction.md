# Task f9_dbg_2: Diagnose and Fix

## 1. Goal
The file `exchange_core/handlers/shock.py` (shown in the section "Buggy Target Files" below) was written for the specification in section 2. It contains **one defect**. The "Bug Report" section gives a short event trace and the first thing that goes wrong when the engine runs it.

Find the defect and return the complete corrected file in the usual `### FILE:` format. Change only what the specification requires: every other behaviour must stay exactly as it is. The file is graded like an ordinary implementation: the public tests (shown in full in the "Public Tests (Visible)" section), targeted checkpoints and hidden event traces are all compared with the behaviour the specification defines.

## 2. Applicable Rules (docs/04_RULEBOOK.md Section 8)
- **R-W1 [Declared].** A PRICE_SHOCK event sets the `mark_price` on the state. The engine then runs the waterfall for each account except `LIQ`, in ascending account-id order.
- **R-W2 [Declared].** For an account with `position != 0`:
  - `avail = free_cash + position * mark_price`
  - `req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)`
  - The account is in breach if `avail < req`.
  - An account with `position == 0` is never in breach.
- **R-W3 [Declared].** Stage 1. If the account is in breach, the engine cancels all resting orders of the account in ascending `prio_seq` order. Each cancel releases the lock to `free_cash` and reports `CANCELLED(order_id, RISK)`.
- **R-W4 [Declared].** After stage 1, the engine computes the breach test again with the new `free_cash`. If the account is not in breach, the engine must not liquidate.
- **R-W5 [Declared].** Stage 2. If the account is still in breach, the engine liquidates the whole position at `mark_price` against the account `LIQ`:
  - If `position > 0`: the account sells `position` units to `LIQ`. The account receives `position * mark_price`. `LIQ` pays the same amount.
  - If `position < 0`: the account buys `abs(position)` units from `LIQ`. The account pays `abs(position) * mark_price`. `LIQ` receives the same amount.
  - The position of the account becomes 0. The position of `LIQ` changes by the opposite amount (`liq.position += orig_position`).
  - No fee applies. The book does not change.
  - The engine reports `LIQUIDATED(account, qty)` where `qty` is the signed position before liquidation.
- **R-W6 [Declared].** The report order for PRICE_SHOCK is: `MARK_SET`, then for each account in ascending order the stage 1 cancels, then the `LIQUIDATED` report if it occurs.

## 3. Interface and Return Value

```python
from exchange_core.types import Event, Report

def handle_shock(engine: Any, event: Event) -> list[Report]:
    """Process PRICE_SHOCK and run margin waterfall for breached accounts."""
```

Returns `list[Report]` in strict order (Rule R-W6):
1. `Report.mark_set(mark_price=event.mark_price)`
2. For each breached account in ascending account-id order:
   - Any Stage 1 cancels: `Report.cancelled(order_id=o.order_id, reason="RISK")` in ascending `prio_seq` order
   - If still in breach after Stage 1, Stage 2 liquidation: `Report.liquidated(account=acc_id, qty=orig_position)`

### The `engine` argument

`engine` is the exchange `Engine` object. A handler may use these members:

- `engine.cfg`: the `EngineConfig` instance. Its fields are listed in the `exchange_core/config.py` context file below.
- `engine.state`: the `EngineState` instance, described in the `exchange_core/state.py` context file below. Handlers read it and change it in place.

The `Engine` class itself is not part of this task. Use only the members listed here; no other attribute of `engine` is available.

## 4. Allowed Dependencies
- `from exchange_core.book import get_account_orders, remove_order`
- `from exchange_core.intmath import ceil_div`
- `from exchange_core.types import Event, Report`

## Allowed imports

You may import standard library modules and the following `exchange_core` modules only:
- `exchange_core.types`
- `exchange_core.state`
- `exchange_core.intmath`
- `exchange_core.config`
- `exchange_core.book`
- `exchange_core.ledger`
- `exchange_core.engine`
- `exchange_core.handlers.new_limit`

All other `exchange_core` imports (including `exchange_core.rules.*`, other handlers like `exchange_core.handlers.shock`, and `exchange_core.rules.waterfall_rule`) are forbidden. Dynamic import calls (`importlib`, `__import__`, `eval`, `exec`) are strictly forbidden. Any violation immediately fails grading with `FORBIDDEN_IMPORT` and a score of 0.
