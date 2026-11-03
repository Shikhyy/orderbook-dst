# Task f3_fix_a: FIX Sequence Rule

## 1. Goal

Implement the pure decision function for FIX session sequence management in `exchange_core/rules/session_rule.py`.
The function processes incoming FIX messages, handles gap filling, drains buffered messages in order, and manages duplicate detection.

## 2. Files

Target file to write:
- `exchange_core/rules/session_rule.py`

The public tests for this task are shown in full in the "Public Tests (Visible)" section of the prompt.

## 3. Interface

```python
from exchange_core.state import SessionState
from exchange_core.types import FixMsg, SessionOutcome

def on_message(session: SessionState, msg: FixMsg) -> SessionOutcome:
    """Process an incoming FIX message according to session sequence rules."""
```

The function returns a `SessionOutcome` instance:
- `to_process`: list of `FixMsg` ready for processing, in sequence order.
- `reports`: list of `Report` emitted directly by the session layer (e.g. `BUFFERED`, `DISCARDED`).

The function updates the mutable `session` state (`next_seq` and `buffer`).

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
- Consecutive messages present in `session.buffer` are drained in ascending sequence order, each incrementing `next_seq` and added to `to_process`.

### R-S5 [Common, FIX semantics]
If `seq > next_seq`:
- If `seq` is already present in `session.buffer`: report `DISCARDED(DUPLICATE_BUFFERED)`.
- Otherwise: store the message in `session.buffer[seq]` and report `BUFFERED`.

## 5. Output format

Provide the complete contents of `exchange_core/rules/session_rule.py` inside a single markdown code block:

```python
### FILE: exchange_core/rules/session_rule.py
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
- Preserve session state mutating contracts (`session.next_seq`, `session.buffer`).
