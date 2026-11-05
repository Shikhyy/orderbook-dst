# Task f9_dbg_4: Diagnose and Fix

## 1. Goal
The file `exchange_core/handlers/new_limit.py` (shown in the section "Buggy Target Files" below) was written for the specification in section 2. It contains **one defect**. The "Bug Report" section gives a short event trace and the first thing that goes wrong when the engine runs it.

Find the defect and return the complete corrected file in the usual `### FILE:` format. Change only what the specification requires: every other behaviour must stay exactly as it is. The file is graded like an ordinary implementation: the public tests (shown in full in the "Public Tests (Visible)" section), targeted checkpoints and hidden event traces are all compared with the behaviour the specification defines.

## 2. Interface

```python
from exchange_core.types import Event, Report

def handle_new_limit(engine: "Engine", event: Event) -> list[Report]:
    """Process a NEW_LIMIT event and return the reports in order."""
```

`event` has `account`, `side` (`"BUY"` or `"SELL"`), `price`, `qty` and `flag` (`"NONE"`, `"IOC"` or `"POST_ONLY"`).

### The `engine` argument

`engine` is the exchange `Engine` object. The handler may use these members:

- `engine.state`: the `EngineState` instance, described in the `exchange_core/state.py` context file below. The handler reads it and changes it in place.
- `engine.cfg`: the `EngineConfig` instance (`engine.cfg.tick` is the tick size).
- `settle_fill(engine, fill)`: imported with `from exchange_core.handlers.settle import settle_fill`. It takes a `Fill` (see `exchange_core/types.py`) and performs R-M4 steps 1, 2, 5 and 6: it moves the cash and the positions, settles fees, rebates and volume, and returns `[Report.fill(...)]`. It does not touch `cum_qty`, locks or the book, and it reads nothing from them: it only reads and changes `accounts` and `fee_vault`. It does not matter whether the handler calls it before or after R-M4 steps 3 and 4.

The `Engine` class itself is not part of this task. Use only the members listed here; no other attribute of `engine` is available.

A resting order is stored in `engine.state.orders[order_id]`. The helpers in `exchange_core/book.py` (`get_asks`, `get_bids`, `best_ask`, `best_bid`, `add_order`, `remove_order`) return the resting orders in priority order. `ceil_div` is in `exchange_core/intmath.py`.

## 3. Rules

**R-B3.** `prio_seq` and `order_id` come from two counters in the state (`state.next_prio_seq`, `state.next_order_id`). Both counters start at 1. The engine does not use time.

**R-B4.** The validation order for a NEW_LIMIT event is:
1. If the account does not exist, return `[Report.rejected("UNKNOWN_ACCOUNT")]`.
2. If `qty <= 0`, or `price <= 0`, or `price % tick != 0`, return `[Report.rejected("INVALID_ORDER")]`.
3. If the flag is `POST_ONLY` and the order would match now, return `[Report.rejected("POST_ONLY_WOULD_CROSS")]`. "Would match now" means that the best price on the opposite side of the book crosses the limit price (a BUY crosses when the best ask is at or below its price; a SELL crosses when the best bid is at or above its price). All resting orders count, including orders of the same account.
4. Compute `lock = ceil_div(qty * price * state.margin_bps, 10000)`. If `free_cash < lock`, return `[Report.rejected("INSUFFICIENT_MARGIN")]`.

A rejected order changes no state. A rejected order does not use a counter value.

**R-B5.** When the order is valid, the handler does these steps in order:
1. Assign `order_id` and `prio_seq` from the counters. Add 1 to each counter.
2. Create the order with `cum_qty = 0`, the event's `flag` stored in it as `flag`, and the current `state.margin_bps` stored in it as `margin_bps`.
3. Subtract `lock` from `free_cash`. Add `lock` to `locked_margin`. Store `lock` in the order.
4. Report `ACCEPTED(order_id)`.
5. Match the order (rules R-M1 to R-M4).
6. If the flag is `IOC` and `leaves > 0`, cancel the remainder with `Report.cancelled(order_id, "IOC_REMAINDER")`. Release the lock of the order: move it from `locked_margin` to `free_cash`. The order is not stored in `state.orders`.
7. If the flag is not `IOC` and `leaves > 0`, add the order to the book as a resting order (it is stored in `state.orders`).

An order that is completely filled is never stored in `state.orders`.

**R-M1.** A BUY order matches SELL resting orders with `price <= limit`. A SELL order matches BUY resting orders with `price >= limit`. The handler matches the best price first. At the same price, it matches the lowest `prio_seq` first. Matching stops when the order has `leaves == 0`, when the book has no resting order on the opposite side, or when the best opposite resting order does not cross the limit price.

**R-M2.** The fill price is the price of the resting order. The fill quantity is the smaller `leaves` of the two orders.

**R-M3.** Self-trade prevention. When the best resting order that crosses the limit price has the same account as the incoming order, the handler cancels that resting order with reason `STP`. It removes it from the book. It moves the full lock of the resting order from `locked_margin` to `free_cash`. It reports `Report.cancelled(order_id, "STP")`. It then continues to match with the next resting order. No fill occurs for the cancelled order.

**R-M4.** Effect of a fill with quantity `q` and price `p`:
1. The buyer pays `q * p` and its position changes. (Done by `settle_fill`.)
2. The seller receives `q * p`. (Done by `settle_fill`.)
3. For each of the two orders, add `q` to `cum_qty`.
4. For each of the two orders, compute `new_lock = ceil_div(leaves * order.price * order.margin_bps, 10000)`, using the `margin_bps` stored in that order. Move `old_lock - new_lock` from `locked_margin` to `free_cash`. Store `new_lock` in the order.
5. Settle the fees. (Done by `settle_fill`.)
6. Report the fill. (Done by `settle_fill`; the handler adds the returned reports to its own list.)

A fill can make `free_cash` negative. This is allowed. A resting order with `leaves == 0` leaves the book.

**R-M5.** When a fill makes `leaves == 0` for an order (including the incoming order), its `new_lock` is 0, so the whole old lock moves from `locked_margin` to `free_cash`.

The handler builds the `Fill` for `settle_fill` with `buy_order_id` and `sell_order_id` of the two orders, the fill `price` and `qty`, `taker_order_id` equal to the incoming order, and `buyer` and `seller` equal to the accounts of the buy order and the sell order.

## 4. Report order
The reports are returned in the order in which the events happen: `ACCEPTED`, then for each step of matching the `STP` cancellation or the `FILL`, then `IOC_REMAINDER` if it applies.

## 5. Allowed imports

You may import standard library modules and the following `exchange_core` modules only:
- `exchange_core.types`
- `exchange_core.state`
- `exchange_core.intmath`
- `exchange_core.config`
- `exchange_core.book`
- `exchange_core.ledger`
- `exchange_core.engine`
- `exchange_core.handlers.settle`

All other `exchange_core` imports (including `exchange_core.rules.*` and other handlers such as `exchange_core.handlers.shock`) are forbidden. Dynamic import calls (`importlib`, `__import__`, `eval`, `exec`) are strictly forbidden. Any violation immediately fails grading with `FORBIDDEN_IMPORT` and a score of 0.

## 6. Output format

Provide the complete contents of `exchange_core/handlers/new_limit.py` in exactly this layout, with the `### FILE:` line above one markdown code block:

### FILE: exchange_core/handlers/new_limit.py
```python
# complete file contents here
```
