# Task f1_fee_a: Fee Tier Rule

## 1. Goal

Implement the pure calculation functions for taker fees and maker rebates in `exchange_core/rules/fee_rule.py`.
The functions calculate the fee and rebate for a fill using tier threshold volume and round-half-even rounding.

## 2. Files

Target file to write:
- `exchange_core/rules/fee_rule.py`

The public tests for this task are shown in full in the "Public Tests (Visible)" section of the prompt.

## 3. Interface

```python
from exchange_core.config import EngineConfig

def compute_taker_fee(volume_before: int, notional: int, cfg: EngineConfig) -> int:
    """Compute the taker fee for a fill using tier threshold logic."""

def compute_maker_rebate(notional: int, cfg: EngineConfig) -> int:
    """Compute the maker rebate for a fill."""
```

Both functions return an integer amount in micro-USD.

## 4. Rules

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
Division that produces a fee, a rebate, or a margin requirement rounds to the nearest integer. If the fractional part is exactly one half (tie), round to the nearest even integer.
Formula: `round_half_even(n, d) = round(n / d)` with round-half-even.

## 5. Output format

Provide the complete contents of `exchange_core/rules/fee_rule.py` inside a single markdown code block:

```python
### FILE: exchange_core/rules/fee_rule.py
...
```

Do not edit or return other files.

## 6. What the grader checks

The grader checks your code against three tiers:
- **Tier 1 (Public tests)**: 8 unit tests shown in the prompt.
- **Tier 2 (Targeted trace)**: 42 events with 7 fill checkpoints (including round-half-even tie break).
- **Tier 3 (Hidden seeds)**: 20 traces of 200 events each under the `fee_heavy` profile.
  Checks invariant I1 (conservation of cash and vault), I2 (margin locks), I3 (order queue integrity), and D1 (differential matching against reference reports).

## 7. Constraints

- Integer arithmetic only. Use integer math helpers (`exchange_core.intmath.round_half_even`).
- Do not import `math` or use float division (`/`).
- Standard library only.
