# Task f1_fee_b: Fill Settlement Handler

## 1. Goal

Implement the fill settlement handler in `exchange_core/handlers/settle.py`.
The handler settles the financial and account changes from an order match: transferring cash, updating positions, computing the tiered taker fee, paying the maker rebate, updating the fee vault, updating volume, and emitting a `FILL` report.

## 2. Files

Target file to write:
- `exchange_core/handlers/settle.py`

The public tests for this task are shown in full in the "Public Tests (Visible)" section of the prompt.

## 3. Interface

```python
from exchange_core.types import Fill, Report

def settle_fill(engine: "Engine", fill: Fill) -> list[Report]:
    """Settle the financial effects of a fill."""
```

The function returns a list containing exactly one `FILL` report:
```python
Report.fill(
    buy_order_id=fill.buy_order_id,
    sell_order_id=fill.sell_order_id,
    price=fill.price,
    qty=fill.qty,
    taker_order_id=fill.taker_order_id,
)
```

## 4. Rules

### R-M4 [Declared]
When an incoming order matches a resting order, the engine executes these settlement steps in order:
1. Buyer pays notional (`price * qty`) from `free_cash`. Buyer position increases by `qty`.
2. Seller receives notional in `free_cash`. Seller position decreases by `qty`.
3. Compute taker fee from taker `volume` before the fill (R-F2).
4. Compute maker rebate (R-F3).
5. Taker pays fee from `free_cash`. Maker receives rebate in `free_cash`. `fee_vault` increases by `fee - rebate`.
6. Buyer and seller each add `notional` to their `volume` (R-F1).
7. Return a `FILL` report with `buy_order_id`, `sell_order_id`, `price`, `qty`, and `taker_order_id`.

### R-F1 [Declared]
The volume of an account is the sum of notional values of all fills in the session where the account was buyer or seller. Fills with zero fee also add to volume. Volume updates after the fee of the current fill is computed.

### R-F2 [Declared]
The taker fee for a fill depends on the volume of the taker account before the fill:
- If `volume_before >= TIER_THRESHOLD`: `fee = round_half_even(notional * TAKER_PPM_T1, PPM)`.
- If `volume_before + notional <= TIER_THRESHOLD`: `fee = round_half_even(notional * TAKER_PPM_T0, PPM)`.
- Otherwise the fill crosses the threshold. Split it:
  `below = TIER_THRESHOLD - volume_before`
  `above = notional - below`
  `fee = round_half_even(below * T0, PPM) + round_half_even(above * T1, PPM)`
The engine rounds each part on its own. It does not round the sum.

### R-F3 [Declared]
The maker rebate for a fill is `round_half_even(notional * MAKER_REBATE_PPM, PPM)`. The rebate is paid from the fee vault to the maker. The rebate does not depend on volume tiers.

### R-U2 [Declared]
Division rounds to the nearest even integer on ties (`round_half_even`).

## 5. Output format

Provide the complete contents of `exchange_core/handlers/settle.py` inside a single markdown code block:

```python
### FILE: exchange_core/handlers/settle.py
...
```

Do not edit or return other files.

## 6. What the grader checks

The grader checks your code against three tiers:
- **Tier 1 (Public tests)**: 9 unit tests shown in the prompt.
- **Tier 2 (Targeted trace)**: 42 events with 7 fill checkpoints (including round-half-even tie break).
- **Tier 3 (Hidden seeds)**: 20 traces of 200 events each under the `fee_heavy` profile.
  Checks invariant I1 (conservation of cash and vault), I2 (margin locks), I3 (order queue integrity), and D1 (differential matching against reference reports).

## 7. Constraints

- Integer arithmetic only. Use `round_half_even` from `exchange_core.intmath`.
- Standard library only.
