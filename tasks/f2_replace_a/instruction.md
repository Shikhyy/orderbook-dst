# Task f2_replace_a: Replace Decision Rule

## 1. Goal

Implement the pure decision function for replace events in `exchange_core/rules/replace_rule.py`.
The function decides whether a replace request is valid and whether the order keeps its place in the priority queue.

## 2. Files

Target file to write:
- `exchange_core/rules/replace_rule.py`

The public tests for this task are shown in full in the "Public Tests (Visible)" section of the prompt.

## 3. Interface

```python
from exchange_core.config import EngineConfig
from exchange_core.types import Order, ReplaceDecision

def decide_replace(
    order: Order,
    new_price: int,
    new_qty: int,
    cfg: EngineConfig,
) -> ReplaceDecision:
    """Decide whether a replace request is valid and whether it keeps priority."""
```

The function returns a `ReplaceDecision` instance:
- `ok`: boolean flag (`True` if valid, `False` if rejected).
- `reason`: string rejection reason (`""` if valid, `"INVALID_ORDER"` or `"INVALID_REPLACE"` if rejected).
- `keep_priority`: boolean flag (`True` if the order keeps priority, `False` if it loses priority).
- `new_leaves`: integer new remaining quantity (`new_qty - order.cum_qty` if valid, `0` if rejected).

## 4. Rules

### R-P1 [Common, FIX semantics]
A REPLACE event carries `order_id`, `new_price`, and `new_qty`. The value `new_qty` is the new total order quantity (the FIX field OrderQty). It is not the new leaves.

### R-P2 [Declared]
The engine rejects a REPLACE event in this order:
1. If the order is not resting: `REJECTED(UNKNOWN_ORDER)`. (Checked by handler)
2. If `new_price <= 0` or `new_price % TICK != 0`: `REJECTED(INVALID_ORDER)`.
3. If `new_qty <= cum_qty`: `REJECTED(INVALID_REPLACE)`.
4. If the new price would match the opposite side of the book: `REJECTED(REPLACE_WOULD_CROSS)`. (Checked by handler)
5. If the new lock is more than the old lock and the difference is more than `free_cash`: `REJECTED(INSUFFICIENT_MARGIN)`. (Checked by handler)

A rejected REPLACE changes no state.

### R-P3 [Common, FIX semantics]
Priority after a valid REPLACE:
- If `new_price` equals the old price and `new_qty` is less than the old `qty`, the order keeps its `prio_seq` and its place in the queue.
- If `new_price` equals the old price and `new_qty` equals the old `qty`, nothing changes.
- In all other cases (price change, or quantity increase), the order gets a new `prio_seq` from the counter and goes to the back of the queue at its price.

## 5. Output format

Provide the complete contents of `exchange_core/rules/replace_rule.py` in exactly this layout, with the `### FILE:` line above one markdown code block:

### FILE: exchange_core/rules/replace_rule.py
```python
...
```

Do not edit or return other files.

## 6. What the grader checks

The grader checks:
1. **Tier 1 (T1)**: Public unit tests shown in the prompt.
2. **Tier 2 (T2)**: Targeted replacement trace checkpoints.
3. **Tier 3 (T3)**: 20 hidden traces evaluated against invariants:
   - I1: Cash conservation.
   - I2: Margin matches resting orders.
   - I3: Position sum is zero.
   - D1: Differential equivalence with reference outputs.

## 7. Constraints

- Use integer arithmetic only. Never use floating-point numbers or operations.
- Do not modify any other file in the repository.

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
