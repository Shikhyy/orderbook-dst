# tests/test_trace_gen.py
# Tests for graders/trace_gen.py.
# Written before implementation (TDD).

import pytest

from graders.trace_gen import PROFILES, TraceResult, generate_trace


class TestTraceGen:
    """Trace generator and profile validation."""

    def test_all_profiles_supported(self):
        expected_profiles = {
            "fee_heavy", "replace_heavy", "fix_noisy", "shock_heavy", "basket_heavy", "match_heavy",
        }
        assert set(PROFILES) == expected_profiles

    @pytest.mark.parametrize("profile", PROFILES)
    def test_trace_generation_structure(self, profile: str):
        res: TraceResult = generate_trace(seed=42, profile=profile, num_events=100)
        assert len(res.events) == 100
        # At least 3 accounts + LIQ
        trading_accounts = [acc for acc in res.accounts if acc != "LIQ"]
        assert len(trading_accounts) >= 3
        assert "LIQ" in res.accounts
        assert res.mark_price > 0
        assert res.trigger_count >= 10

    @pytest.mark.parametrize("profile", PROFILES)
    def test_trace_determinism(self, profile: str):
        t1 = generate_trace(seed=101, profile=profile, num_events=50)
        t2 = generate_trace(seed=101, profile=profile, num_events=50)
        assert t1.events == t2.events
        assert t1.accounts == t2.accounts
        assert t1.trigger_count == t2.trigger_count

    def test_invalid_event_frequency(self):
        # Around 3% of events should be invalid across a large trace
        res = generate_trace(seed=7, profile="replace_heavy", num_events=1000)
        # Check invalid events flagged in trace result or present in trace
        assert 10 <= res.invalid_count <= 60  # ~3% of 1000 = ~30
