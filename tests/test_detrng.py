# tests/test_detrng.py
# Tests for graders/detrng.py (xorshift64* deterministic RNG).
# Written before implementation (TDD).

from graders.detrng import DetRng


class TestDetRng:
    """Deterministic random number generator tests."""

    def test_determinism_same_seed(self):
        rng1 = DetRng(12345)
        rng2 = DetRng(12345)
        vals1 = [rng1.next_u64() for _ in range(100)]
        vals2 = [rng2.next_u64() for _ in range(100)]
        assert vals1 == vals2

    def test_different_seeds_differ(self):
        rng1 = DetRng(12345)
        rng2 = DetRng(54321)
        vals1 = [rng1.next_u64() for _ in range(20)]
        vals2 = [rng2.next_u64() for _ in range(20)]
        assert vals1 != vals2

    def test_zero_seed_handled_safely(self):
        # xorshift cannot have state 0; seed 0 should be mapped to non-zero
        rng = DetRng(0)
        v = rng.next_u64()
        assert v != 0
        v2 = rng.next_u64()
        assert v2 != v

    def test_next_int_range(self):
        rng = DetRng(999)
        for _ in range(200):
            val = rng.next_int(10, 20)
            assert 10 <= val <= 20

    def test_choice(self):
        rng = DetRng(42)
        items = ["A", "B", "C", "D"]
        chosen = {rng.choice(items) for _ in range(100)}
        assert chosen == {"A", "B", "C", "D"}

    def test_prob_pct(self):
        rng = DetRng(777)
        # 0% should always be False
        assert not any(rng.prob_pct(0) for _ in range(50))
        # 100% should always be True
        assert all(rng.prob_pct(100) for _ in range(50))
