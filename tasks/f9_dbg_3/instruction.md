# Task f9_dbg_3: Diagnose and Fix

## 1. Goal
The file `exchange_core/handlers/basket.py` (shown in the section "Buggy Target Files" below) was written for the specification in section 2. It contains **one defect**. The "Bug Report" section gives a short event trace and the first thing that goes wrong when the engine runs it.

Find the defect and return the complete corrected file in the usual `### FILE:` format. Change only what the specification requires: every other behaviour must stay exactly as it is. The file is graded like an ordinary implementation: the public tests (shown in full in the "Public Tests (Visible)" section), targeted checkpoints and hidden event traces are all compared with the behaviour the specification defines.

## 2. Applicable Rules (docs/04_RULEBOOK.md Section 10)
- **R-A1 [Declared].** A BASKET event carries an `account` and a list of legs (`event.legs`). A leg has `side`, `price`, `qty`, and `flag` (`IOC` or `POST_ONLY`).
- **R-A2 [Declared].** The engine takes a snapshot of the complete state before leg 1. It then processes each leg in order as a `NEW_LIMIT` event for the account.
- **R-A3 [Declared].**
  - An `IOC` leg succeeds if it is accepted and `leaves` is 0 after matching (it must not have an `IOC_REMAINDER` cancellation).
  - A `POST_ONLY` leg succeeds if it is accepted (it must not cross).
  - A rejected leg fails.
- **R-A4 [Declared].** If a leg fails, the engine stops. It restores the snapshot. The restore covers the book, all accounts, `fee_vault`, all `volume` values, both counters (`next_order_id`, `next_prio_seq`), and `mark_price`. The engine reports only `BASKET_ROLLED_BACK(leg_index)` (0-based index of the failing leg). The reports of earlier legs are discarded.
- **R-A5 [Declared].** If all legs succeed, the engine reports the reports of all legs in order, then `BASKET_COMMITTED`.

## 3. Interface and Return Value

```python
from exchange_core.types import Event, Report

def handle_basket(engine: Any, event: Event) -> list[Report]:
    """Process atomic multi-leg basket order with rollback semantics."""
```

Returns `list[Report]`:
- If any leg fails: `[Report.basket_rolled_back(leg_index=failing_leg_index)]` (0-based index of failing leg).
- If all legs succeed: reports of all individual legs in order, followed by `Report.basket_committed()`.

### The `engine` argument

`engine` is the exchange `Engine` object. A handler may use these members:

- `engine.state`: the `EngineState` instance, described in the `exchange_core/state.py` context file below. Handlers read it and change it in place.
- `engine.dispatch(event: Event) -> list[Report]`: runs the event through the engine's own handler for `event.kind` and returns its reports. `engine.process(event)` does exactly the same.

The `Engine` class itself is not part of this task. Use only the members listed here; no other attribute of `engine` is available.

## 4. Allowed Dependencies
- `from exchange_core.types import Event, Report`
- Call `engine.dispatch(event: Event) -> list[Report]` or `handle_new_limit(engine: "Engine", event: Event) -> list[Report]` for each leg event.
- Use `engine.state.snapshot()` and `engine.state.restore(snap)` for state rollback.

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
