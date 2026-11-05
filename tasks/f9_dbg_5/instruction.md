# Task f9_dbg_5: Diagnose and Fix

## 1. Goal
The file `exchange_core/handlers/funding.py` (shown in the section "Buggy Target Files" below) was written for the specification in section 2. It contains **one defect**. The "Bug Report" section gives a short event trace and the first thing that goes wrong when the engine runs it.

Find the defect and return the complete corrected file in the usual `### FILE:` format. Change only what the specification requires: every other behaviour must stay exactly as it is. The file is graded like an ordinary implementation: the public tests (shown in full in the "Public Tests (Visible)" section), targeted checkpoints and hidden event traces are all compared with the behaviour the specification defines.

## 2. Interface

```python
from exchange_core.types import Event, Report

def handle_funding(engine: "Engine", event: Event) -> list[Report]:
    """Apply funding payments and return the reports in order."""
```

For a FUNDING event, `event.bps` holds the funding rate in **parts per million** (it can be negative). The other event fields are not used.

### The `engine` argument

`engine` is the exchange `Engine` object. The handler may use these members:

- `engine.state`: the `EngineState` instance, described in the `exchange_core/state.py` context file below. The handler reads it and changes it in place. The current mark price is `engine.state.mark_price`.
- `engine.cfg`: the `EngineConfig` instance. `engine.cfg.ppm` is the divisor for parts per million (1,000,000).
- `engine.dispatch(event: Event) -> list[Report]`: runs the event through the engine's own handler for `event.kind` and returns its reports. `engine.process(event)` does exactly the same.

The `Engine` class itself is not part of this task. Use only the members listed here; no other attribute of `engine` is available. `round_half_even` is in `exchange_core/intmath.py`; its documented precondition is `n >= 0`.

## 3. Rules

**R-Y1.** The engine clamps the rate to the range -3000 to +3000, both limits included. The clamped value is `rate`.

**R-Y2.** If `rate != 0`, the engine processes every account with `position != 0`, in ascending account-id order (the `LIQ` account is included). For each such account:
- `notional = abs(position) * mark_price`
- `amount = round_half_even(notional * abs(rate), ppm)`. The rounding is applied to this non-negative value.
- The account **pays** `amount` when it is long and `rate > 0`, or short and `rate < 0`. In every other case it **receives** `amount`.
- A payment is subtracted from `free_cash`. A receipt is added to `free_cash`. `free_cash` can become negative.

Locks, volume and positions do not change.

**R-Y3.** The rounding is done per account, so the payments and receipts need not cancel. The engine adds the net of all payments (payments minus receipts; the net can be negative) to `state.fee_vault`. Total cash plus `fee_vault` is therefore unchanged.

**R-Y4.** The first report is `Report(kind="FUNDING_APPLIED", bps=rate, qty=n)`, where `rate` is the clamped rate and `n` is the number of accounts processed in R-Y2. If `rate == 0`, R-Y2 processes no account, so `n = 0` (even if some accounts hold positions). If `rate != 0`, `n` counts every account with `position != 0`, including an account whose `amount` rounds to 0.

**R-Y5.** After the payments, the engine always runs the margin waterfall at the current mark price: it dispatches `Event(kind="PRICE_SHOCK", mark_price=state.mark_price)` through `engine.dispatch` and appends the returned reports, in their own order, after `FUNDING_APPLIED`. This also happens when `rate == 0`.

## 4. Allowed imports

You may import standard library modules and the following `exchange_core` modules only:
- `exchange_core.types`
- `exchange_core.state`
- `exchange_core.intmath`
- `exchange_core.config`
- `exchange_core.book`
- `exchange_core.ledger`
- `exchange_core.engine`

All other `exchange_core` imports (including `exchange_core.rules.*` and other handlers such as `exchange_core.handlers.shock`) are forbidden. Dynamic import calls (`importlib`, `__import__`, `eval`, `exec`) are strictly forbidden. Any violation immediately fails grading with `FORBIDDEN_IMPORT` and a score of 0.

## 5. Output format

Provide the complete contents of `exchange_core/handlers/funding.py` in exactly this layout, with the `### FILE:` line above one markdown code block:

### FILE: exchange_core/handlers/funding.py
```python
# complete file contents here
```
