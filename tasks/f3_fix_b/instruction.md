# Task f3_fix_b: FIX Session Handler

## 1. Goal

Implement the FIX message and session reset handler in `exchange_core/handlers/fix.py`.
The handler manages session lifecycle (`SESSION_RESET`) and sequences incoming messages (`FIX_MSG`), dispatching in-order message bodies to the engine and emitting session reports.

## 2. Files

Target file to write:
- `exchange_core/handlers/fix.py`

The public tests for this task are shown in full in the "Public Tests (Visible)" section of the prompt.

## 3. Interface

```python
from exchange_core.types import Event, Report

def handle_fix(engine: "Engine", event: Event) -> list[Report]:
    """Handle FIX session events (FIX_MSG and SESSION_RESET)."""
```

Method on `engine` to dispatch message bodies (copied from `exchange_core/engine.py`):
```python
def dispatch(self, event: Event) -> list[Report]:
```

The function returns a list of `Report` instances.

## 4. Rules

### R-S1 [Common, FIX semantics]
A FIX session has an `epoch` counter and a `next_seq` counter. Both start at 1. Each message has: `session`, `epoch`, `seq`, `poss_dup`, and `body`.

### R-S2 [Common, FIX semantics]
The engine rejects messages with `epoch != session.epoch` with `DISCARDED(EPOCH)`.

### R-S3 [Common, FIX semantics]
If `seq < next_seq`:
- If `poss_dup == True`: report `DISCARDED(DUPLICATE)`.
- If `poss_dup == False`: report `DISCARDED(SEQ_TOO_LOW)`.

### R-S4 [Common, FIX semantics]
If `seq == next_seq`:
- The message is accepted for processing, even if `poss_dup == True`.
- `next_seq` increases by 1.
- Consecutive messages present in `session.buffer` are drained in ascending sequence order, each incrementing `next_seq` and dispatched via `engine.dispatch(body)`.

### R-S5 [Common, FIX semantics]
If `seq > next_seq`:
- If `seq` is already present in `session.buffer`: report `DISCARDED(DUPLICATE_BUFFERED)`.
- Otherwise: store the message in `session.buffer[seq]` and report `BUFFERED`.

### R-S8 [Declared]
On `SESSION_RESET`:
- `session.epoch += 1`
- `session.next_seq = 1`
- `session.buffer.clear()`
- Return `[Report.session_reset_done(session)]`.

### R-S9 [Declared]
When message bodies are dispatched, the resulting reports are accumulated in order: the incoming message body reports first, followed by each drained buffered message's reports in ascending sequence order.

## 5. Output format

Provide the complete contents of `exchange_core/handlers/fix.py` inside a single markdown code block:

```python
### FILE: exchange_core/handlers/fix.py
...
```

Do not edit or return other files.

## 6. What the grader checks

The grader checks your code against three tiers:
- **Tier 1 (Public tests)**: 9 unit tests shown in the prompt.
- **Tier 2 (Targeted trace)**: Targeted trace with message gaps, duplicates, buffer drain, and reset checkpoints.
- **Tier 3 (Hidden seeds)**: 20 traces of 200 events each under the `fix_noisy` profile, including the Invariant I4 replay law check.
  Checks invariants I1, I2, I3, I4, and D1.

## 7. Constraints

- Standard library only.

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
