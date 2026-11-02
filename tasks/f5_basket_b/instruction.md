# Task f5_basket_b: Atomic Basket Order Handler

## 1. Goal
Implement the atomic basket handler function:
```python
def handle_basket(engine: Any, event: Event) -> list[Report]:
```
in `exchange_core/handlers/basket.py`.

## 2. Applicable Rules (docs/04_RULEBOOK.md Section 10)
- **R-A1 [Declared].** A BASKET event carries an `account` and a list of legs (`event.legs`). A leg has `side`, `price`, `qty`, and `flag` (`IOC` or `POST_ONLY`).
- **R-A2 [Declared].** The engine takes a snapshot of the complete state before leg 1. It then processes each leg in order as a `NEW_LIMIT` event for the account.
- **R-A3 [Declared].**
  - An `IOC` leg succeeds if it is accepted and `leaves` is 0 after matching (it must not have an `IOC_REMAINDER` cancellation).
  - A `POST_ONLY` leg succeeds if it is accepted (it must not cross).
  - A rejected leg fails.
- **R-A4 [Declared].** If a leg fails, the engine stops. It restores the snapshot. The restore covers the book, all accounts, `fee_vault`, all `volume` values, both counters (`next_order_id`, `next_prio_seq`), and `mark_price`. The engine reports only `BASKET_ROLLED_BACK(leg_index)` (0-based index of the failing leg). The reports of earlier legs are discarded.
- **R-A5 [Declared].** If all legs succeed, the engine reports the reports of all legs in order, then `BASKET_COMMITTED`.

## 3. Allowed Dependencies
- `from exchange_core.types import Event, Report`
- Call `engine.dispatch(...)` or `handle_new_limit(...)` for each leg event.
- Use `engine.state.snapshot()` and `engine.state.restore(snap)` for state rollback.
