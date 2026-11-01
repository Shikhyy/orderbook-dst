# tests/test_property_m3.py
# Property tests for trace generator, invariant preservation, I4 replay, and basket rollback.
# Written before implementation (TDD).

import pytest
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.invariants import check_invariants
from graders.trace_gen import PROFILES, generate_trace, make_noisy_fix_trace


class TestPropertyM3:
    """Property tests for Milestone M3."""

    @pytest.mark.parametrize("profile", PROFILES)
    def test_invariants_hold_on_traces(self, profile: str):
        """Property 1: I1, I2, and I3 hold after each event across profiles."""
        for seed in (101, 102, 103):
            trace = generate_trace(seed=seed, profile=profile, num_events=100)
            assert trace.trigger_count >= 10, f"Profile {profile} seed {seed} trigger count < 10"

            cfg = EngineConfig()
            if profile == "fee_heavy":
                # Low threshold for fee_heavy to ensure frequent tier crossings
                cfg = EngineConfig(tier_threshold=100_000_000)

            engine = Engine(cfg, trace.accounts, trace.mark_price)
            for idx, event in enumerate(trace.events):
                engine.process(event)
                violations = check_invariants(engine.state, idx, cfg)
                assert not violations, (
                    f"Violation in {profile} seed {seed} at event {idx} ({event.kind}): "
                    f"{[v.message for v in violations]}"
                )

    def test_i4_replay_property(self):
        """Property 2 (I4): Replay of noisy FIX trace gives identical state hash as clean trace."""
        for seed in (201, 202, 203):
            clean_trace = generate_trace(seed=seed, profile="fix_noisy", num_events=60, clean_fix=True)
            noisy_trace = make_noisy_fix_trace(clean_trace, seed=seed)

            cfg = EngineConfig()
            # Run clean trace
            engine_clean = Engine(cfg, clean_trace.accounts, clean_trace.mark_price)
            for event in clean_trace.events:
                engine_clean.process(event)

            # Run noisy trace
            engine_noisy = Engine(cfg, clean_trace.accounts, clean_trace.mark_price)
            for event in noisy_trace.events:
                engine_noisy.process(event)

            assert engine_clean.state_hash() == engine_noisy.state_hash(), (
                f"I4 failure on seed {seed}: clean and noisy state hashes differ"
            )

    def test_basket_rollback_property(self):
        """Property 3: Rolled-back basket leaves the state hash strictly unchanged."""
        trace = generate_trace(seed=301, profile="basket_heavy", num_events=100)
        cfg = EngineConfig()
        engine = Engine(cfg, trace.accounts, trace.mark_price)

        for event in trace.events:
            if event.kind == "BASKET":
                h_before = engine.state_hash()
                reps = engine.process(event)
                if any(r.kind == "BASKET_ROLLED_BACK" for r in reps):
                    h_after = engine.state_hash()
                    assert h_after == h_before, "State hash changed after rolled-back basket"
            else:
                engine.process(event)
