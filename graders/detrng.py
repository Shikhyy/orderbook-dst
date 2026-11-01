"""graders/detrng.py
Deterministic 64-bit random number generator using the xorshift64* algorithm.
See docs/03_ARCHITECTURE.md section 6 and docs/07_GRADER_SPEC.md section 4.
Independent of Python version and platform.
"""
from typing import Sequence, TypeVar

T = TypeVar("T")

MASK64 = 0xFFFFFFFFFFFFFFFF
MULTIPLIER = 0x2545F4914F6CDD1D
DEFAULT_SEED = 0x853C49E6748FEA9B


class DetRng:
    """Deterministic 64-bit pseudo-random number generator."""

    def __init__(self, seed: int) -> None:
        """Initialize generator with an integer seed."""
        # State must be a non-zero 64-bit integer
        s = seed & MASK64
        if s == 0:
            s = DEFAULT_SEED
        self.state: int = s

    def next_u64(self) -> int:
        """Advance state using xorshift64* and return 64-bit unsigned integer."""
        x = self.state
        x = (x ^ ((x >> 12) & MASK64)) & MASK64
        x = (x ^ ((x << 25) & MASK64)) & MASK64
        x = (x ^ ((x >> 27) & MASK64)) & MASK64
        self.state = x
        return (x * MULTIPLIER) & MASK64

    def next_int(self, low: int, high: int) -> int:
        """Return a random integer in [low, high] inclusive."""
        if low > high:
            low, high = high, low
        span = high - low + 1
        return low + (self.next_u64() % span)

    def choice(self, seq: Sequence[T]) -> T:
        """Choose an element uniformly from a non-empty sequence."""
        if not seq:
            raise IndexError("Cannot choose from an empty sequence")
        idx = self.next_int(0, len(seq) - 1)
        return seq[idx]

    def prob_pct(self, pct: int) -> bool:
        """Return True with probability pct percent (0 to 100)."""
        if pct <= 0:
            return False
        if pct >= 100:
            return True
        return self.next_int(0, 99) < pct

    def shuffle(self, lst: list) -> None:
        """Shuffle a list in-place deterministically (Fisher-Yates)."""
        for i in range(len(lst) - 1, 0, -1):
            j = self.next_int(0, i)
            lst[i], lst[j] = lst[j], lst[i]
