# 05 Invariants and Data Model

## 1. Data types

```python
@dataclass
class Account:
    free_cash: int
    locked_margin: int
    position: int
    volume: int

@dataclass
class Order:
    order_id: int; account: str; side: str          # "BUY" or "SELL"
    price: int; qty: int; cum_qty: int
    prio_seq: int; margin_bps: int; lock: int; flag: str

@dataclass
class SessionState:
    epoch: int; next_seq: int; buffer: dict[int, FixMsg]

@dataclass
class EngineState:
    accounts: dict[str, Account]
    orders: dict[int, Order]          # resting orders by order_id
    fee_vault: int
    next_order_id: int; next_prio_seq: int
    margin_bps: int; mark_price: int
    sessions: dict[str, SessionState]
    initial_total: int                # sum(free_cash + locked_margin) at start
```

Events are frozen dataclasses with a `kind` field.
Event kinds: `NEW_LIMIT`, `CANCEL`, `REPLACE`, `SET_MARGIN_RATE`, `PRICE_SHOCK`, `FIX_MSG`, `SESSION_RESET`, `BASKET`.
Each event type has the fields in `docs/04_RULEBOOK.md`.

The book is a derived view of `orders`. `book.py` builds price levels from `orders` and `prio_seq`.

## 2. Invariants

The grader checks I1, I2, and I3 after each event. It checks I4 on a whole trace.

| ID | Plain-language name | Statement |
|---|---|---|
| I1 | No money created or destroyed | The sum over all accounts of `free_cash + locked_margin`, plus `fee_vault`, equals `initial_total`. |
| I2 | Margin matches resting orders | For each account, `locked_margin` equals the sum of `lock` of its resting orders. For each resting order, `lock` equals `ceil_div(leaves * price * margin_bps, 10000)`. |
| I3 | Book is sound | See the list below. |
| I4 | Replay gives the same state | A trace with duplicate or reordered FIX messages gives the same state hash as the clean trace, if both traces deliver the same set of (epoch, seq) messages and no gap remains. |

I3 has these parts:
1. `best_bid < best_ask` when both exist.
2. Each resting order has `leaves > 0`.
3. In each price level, orders in queue order have strictly rising `prio_seq`.
4. No two orders have the same `prio_seq` or the same `order_id`.
5. Each resting order has a valid price (positive, multiple of `TICK`).

## 3. Violation record

```python
@dataclass
class Violation:
    invariant: str        # "I1" ... "I4"
    plain_name: str
    event_index: int
    message: str          # example: "ledger locked=4200000, resting obligation=3100000"
    diff: dict            # fields that differ
```

## 4. Differential check (D1)

For each seed, the grader runs the reference and the candidate on the same trace.
The two runs must give the same list of reports for each event.
The two runs must give the same final balances, positions, and resting orders (sorted by `order_id`).
The grader does not compare `prio_seq` values or the full state hash between the reference and the candidate.
The grader compares the full state hash only between two runs of the candidate (I4 and the rollback test).

Note: Reports include `order_id` values. The rulebook defines `order_id` assignment, so the values are the same for all correct solutions.

## 5. Canonical state hash

1. Build a dictionary with these keys: `accounts`, `orders`, `fee_vault`, `next_order_id`, `next_prio_seq`, `margin_bps`, `mark_price`, `sessions`.
2. Sort accounts by id. Sort orders by `order_id`. Sort sessions by id. Sort buffers by `seq`.
3. Convert to JSON with `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`.
4. Return the SHA-256 hex digest of the UTF-8 bytes.

## 6. Scenario setup

A scenario gives: the list of accounts with their start cash, the `LIQ` account with a large start cash, the start `mark_price`, and the `EngineConfig`.
`initial_total` is the sum of `free_cash` of all accounts at the start.
