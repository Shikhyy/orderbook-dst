"""exchange_core/intmath.py
Integer arithmetic helpers.

Rule R-U1: All amounts, prices, and quantities are integers.
No other module does rounding.
No float is used. No bare / operator is used.
"""


def round_half_even(n: int, d: int) -> int:
    """Divide n by d and round to the nearest integer.

    Rule R-U2: When the result is exactly halfway, round to the even integer.

    Algorithm:
      Let q, r = divmod(n, d).
      If 2*r > d:  return q + 1.
      If 2*r == d: return q + (q % 2).   # q is odd -> +1, q is even -> +0
      Otherwise:   return q.

    Preconditions: n >= 0, d > 0.
    """
    q, r = divmod(n, d)
    if 2 * r > d:
        return q + 1
    if 2 * r == d:
        return q + (q % 2)
    return q


def ceil_div(n: int, d: int) -> int:
    """Return the smallest integer that is not below n / d.

    Rule R-U3: Equals -((-n) // d).

    Preconditions: n >= 0, d > 0.
    """
    return -((-n) // d)
