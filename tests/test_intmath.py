# tests/test_intmath.py
# Tests for R-U2 (round_half_even) and R-U3 (ceil_div).
# Written before the implementation (TDD).

import pytest
from exchange_core.intmath import ceil_div, round_half_even


class TestRoundHalfEven:
    """Rule R-U2: round_half_even(n, d) rounds to the nearest integer.
    When the result is exactly halfway, it rounds to the even integer.
    """

    # ---- Worked examples from the rulebook ----

    def test_rulebook_example_25_10(self):
        """round_half_even(25, 10) == 2  (halfway, 2 is even)."""
        assert round_half_even(25, 10) == 2

    def test_rulebook_example_35_10(self):
        """round_half_even(35, 10) == 4  (halfway, 4 is even)."""
        assert round_half_even(35, 10) == 4

    def test_rulebook_example_26_10(self):
        """round_half_even(26, 10) == 3  (above halfway, round up)."""
        assert round_half_even(26, 10) == 3

    # ---- R-F2 fee worked example ----

    def test_fee_below_threshold(self):
        """30,000 * 2,750 / 1,000,000 = 82.5 -> rounds to 82 (82 is even)."""
        assert round_half_even(30_000 * 2_750, 1_000_000) == 82

    def test_fee_above_threshold(self):
        """299,970,000 * 1,850 / 1,000,000 = 554,944.5 -> rounds to 554,944 (even)."""
        assert round_half_even(299_970_000 * 1_850, 1_000_000) == 554_944

    # ---- General cases ----

    def test_round_down(self):
        """Result is below halfway: round down."""
        assert round_half_even(24, 10) == 2

    def test_round_up(self):
        """Result is above halfway: round up."""
        assert round_half_even(26, 10) == 3

    def test_exact_integer(self):
        """No remainder: return the exact quotient."""
        assert round_half_even(30, 10) == 3

    def test_halfway_odd_quotient(self):
        """Halfway with odd quotient (q=1): round up to 2."""
        assert round_half_even(15, 10) == 2

    def test_halfway_even_quotient(self):
        """Halfway with even quotient (q=4): keep 4."""
        assert round_half_even(45, 10) == 4

    def test_zero_numerator(self):
        """n == 0 returns 0."""
        assert round_half_even(0, 10) == 0

    def test_large_values(self):
        """Large values do not overflow (pure integer arithmetic)."""
        n = 554_944_500_000
        d = 1_000_000
        # 554944.5 -> even is 554944
        assert round_half_even(n, d) == 554_944

    def test_rebate_example(self):
        """300,000,000 * 250 / 1,000,000 = 75,000.0 -> 75000."""
        assert round_half_even(300_000_000 * 250, 1_000_000) == 75_000


class TestCeilDiv:
    """Rule R-U3: ceil_div(n, d) returns the smallest integer >= n/d."""

    def test_exact(self):
        """No remainder: quotient equals n/d."""
        assert ceil_div(10, 5) == 2

    def test_one_remainder(self):
        """Remainder 1: rounds up."""
        assert ceil_div(11, 5) == 3

    def test_d_minus_one_remainder(self):
        """Remainder d-1: rounds up."""
        assert ceil_div(14, 5) == 3

    def test_zero_numerator(self):
        """n == 0 returns 0."""
        assert ceil_div(0, 7) == 0

    def test_margin_lock_example(self):
        """qty=6, price=100_000_000, margin_bps=2000, d=10000.
        6 * 100_000_000 * 2000 / 10000 = 120,000,000 exactly.
        """
        assert ceil_div(6 * 100_000_000 * 2_000, 10_000) == 120_000_000

    def test_margin_lock_non_exact(self):
        """When result is not exact, ceil_div rounds up."""
        # 7 * 100_000_000 * 2000 = 1_400_000_000_000 / 10_000 = 140_000_000 exactly
        assert ceil_div(7 * 100_000_000 * 2_000, 10_000) == 140_000_000

    def test_ceil_vs_floor(self):
        """ceil_div(1, 3) == 1, not 0."""
        assert ceil_div(1, 3) == 1

    def test_large_values(self):
        """Large values: no overflow with integer arithmetic."""
        assert ceil_div(10 * 100_000_000 * 2_000, 10_000) == 200_000_000
