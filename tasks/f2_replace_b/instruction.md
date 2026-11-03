# Task f2_replace_b: Replace Handler

## 1. Goal

Implement the complete replace event handler in `exchange_core/handlers/replace.py`.
The handler processes `REPLACE` events according to rules R-P1 to R-P4, adjusts order records, updates ledger locks, and manages priority sequences.

## 2. Files

Target file to write:
- `exchange_core/handlers/replace.py`

The public tests for this task are shown in full in the "Public Tests (Visible)" section of the prompt.

## 3. Interface

```python
from exchange_core.types import Event, Report

def handle_replace(engine: "Engine", event: Event) -> list[Report]:
    """Process a REPLACE event according to rules R-P1 to R-P4."""
```

The function returns a list of `Report` instances:
- On rejection: `[Report.rejected(reason)]`
- On success: `[Report.replaced(order_id)]`

## 4. Rules

### R-P1 [Common, FIX semantics]
A REPLACE event carries `order_id`, `new_price`, and `new_qty`. The value `new_qty` is the new total order quantity (the FIX field OrderQty). It is not the new leaves.

### R-P2 [Declared]
The engine rejects a REPLACE event in this order:
1. If the order is not resting: `REJECTED(UNKNOWN_ORDER)`.
2. If `new_price <= 0` or `new_price % TICK != 0`: `REJECTED(INVALID_ORDER)`.
3. If `new_qty <= cum_qty`: `REJECTED(INVALID_REPLACE)`.
4. If the new price would match the opposite side of the book: `REJECTED(REPLACE_WOULD_CROSS)`.
5. If the new lock is more than the old lock and the difference is more than `free_cash`: `REJECTED(INSUFFICIENT_MARGIN)`.

A rejected REPLACE changes no state.

### R-P3 [Common, FIX semantics]
Priority after a valid REPLACE:
- If `new_price` equals the old price and `new_qty` is less than the old `qty`, the order keeps its `prio_seq` and its place in the queue.
- If `new_price` equals the old price and `new_qty` equals the old `qty`, nothing changes.
- In all other cases (price change, or quantity increase), the order gets a new `prio_seq` from the counter and goes to the back of the queue at its price.

### R-P4 [Declared]
After a valid REPLACE:
- The order keeps its `order_id`, `cum_qty`, and `margin_bps`.
- `qty` becomes `new_qty`. `price` becomes `new_price`.
- The new lock is `ceil_div(new_leaves * new_price * order.margin_bps, 10000)`. The rate is the rate stored in the order. It is not the current rate of the engine.
- The engine moves the difference between the old lock and the new lock between `free_cash` and `locked_margin`.
- The engine reports `REPLACED(order_id)`.

### R-U3 [Declared]
`ceil_div(n, d) = (n + d - 1) // d` for positive integers. If `n == 0`, the result is `0`.

## 5. Output format

Provide the complete contents of `exchange_core/handlers/replace.py`.

## 6. What the grader checks

The grader checks:
1. **Tier 1 (T1)**: 10 public unit tests shown in the prompt.
2. **Tier 2 (T2)**: Targeted replacement trace checkpoints.
3. **Tier 3 (T3)**: 20 hidden traces evaluated against invariants:
   - I1: Cash conservation.
   - I2: Margin matches resting orders.
   - I3: Position sum is zero.
   - D1: Differential equivalence with reference outputs.

## 7. Constraints

- Use integer arithmetic only. Never use floating-point numbers or operations.
- Do not modify any other file in the repository.
