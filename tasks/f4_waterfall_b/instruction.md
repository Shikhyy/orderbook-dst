# Task f4_waterfall_b: Margin Waterfall Handler

## 1. Goal
Implement the margin waterfall handler function:
```python
def handle_shock(engine: Any, event: Event) -> list[Report]:
```
in `exchange_core/handlers/shock.py`.

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

## 3. Allowed Dependencies
- `from exchange_core.book import get_account_orders, remove_order`
- `from exchange_core.intmath import ceil_div`
- `from exchange_core.types import Event, Report`
