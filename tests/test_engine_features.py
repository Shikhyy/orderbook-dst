# tests/test_engine_features.py
# Tests for Self-Trade Prevention (R-M3), FIX Session (R-S), Basket (R-A), and Invariants (I1-I3).
# Written before implementation (TDD).

import pytest
from exchange_core.config import EngineConfig
from exchange_core.types import Event, Report, BasketLeg
from exchange_core.engine import Engine
from exchange_core.invariants import check_invariants


class TestSTP:
    """Rule R-M3: Self-Trade Prevention."""

    def test_stp_cancels_resting_order_and_continues(self):
        cfg = EngineConfig()
        accounts = {"A1": 10_000_000_000, "A2": 10_000_000_000, "LIQ": 10_000_000_000}
        engine = Engine(cfg, accounts, mark_price=100_000_000)

        # A1 places resting SELL order at 100_000_000
        engine.process(Event(kind="NEW_LIMIT", account="A1", side="SELL", price=100_000_000, qty=5))
        assert 1 in engine.state.orders

        # A2 places resting SELL order at 100_000_000
        engine.process(Event(kind="NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=5))
        assert 2 in engine.state.orders

        # A1 places incoming BUY order at 100_000_000 for 5 units
        # Order 1 (same account A1) is cancelled with reason STP.
        # Order 2 (account A2) fills!
        reps = engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=5))

        assert Report.accepted(3) in reps
        assert Report.cancelled(1, "STP") in reps
        assert any(r.kind == "FILL" and r.sell_order_id == 2 for r in reps)
        assert 1 not in engine.state.orders
        assert 2 not in engine.state.orders  # fully filled

        violations = check_invariants(engine.state, 3)
        assert not violations


class TestFixSession:
    """Rules R-S1 to R-S9: FIX session sequence and buffering."""

    def test_in_order_and_gaps(self):
        cfg = EngineConfig()
        accounts = {"A1": 10_000_000_000, "LIQ": 10_000_000_000}
        engine = Engine(cfg, accounts, mark_price=100_000_000)

        body1 = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=1)
        body2 = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=2)
        body3 = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=3)

        # Send seq 1: processed immediately
        reps1 = engine.process(Event(kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=False, body=body1))
        assert Report.accepted(1) in reps1

        # Send seq 3: out of order (gap at seq 2) -> BUFFERED
        reps3 = engine.process(Event(kind="FIX_MSG", session="S1", epoch=0, seq=3, poss_dup=False, body=body3))
        assert reps3 == [Report.buffered()]
        assert 3 in engine.state.sessions["S1"].buffer

        # Send duplicate seq 1 (poss_dup=True) -> DISCARDED(DUPLICATE)
        reps_dup = engine.process(Event(kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=True, body=body1))
        assert reps_dup == [Report.discarded("DUPLICATE")]

        # Send seq 2: fills gap, processes seq 2, then drains seq 3
        reps2 = engine.process(Event(kind="FIX_MSG", session="S1", epoch=0, seq=2, poss_dup=False, body=body2))
        assert Report.accepted(2) in reps2
        assert Report.accepted(3) in reps2
        assert len(engine.state.sessions["S1"].buffer) == 0

        # Session reset
        reps_reset = engine.process(Event(kind="SESSION_RESET", session="S1"))
        assert reps_reset == [Report.session_reset_done("S1")]
        assert engine.state.sessions["S1"].epoch == 1
        assert engine.state.sessions["S1"].next_seq == 1


class TestBasket:
    """Rules R-A1 to R-A5: Atomic basket execution."""

    def test_basket_commit_all_succeed(self):
        cfg = EngineConfig()
        accounts = {"A1": 10_000_000_000, "A2": 10_000_000_000, "LIQ": 10_000_000_000}
        engine = Engine(cfg, accounts, mark_price=100_000_000)

        # Place resting SELL for A2
        engine.process(Event(kind="NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=5))

        # Basket with 2 legs for A1:
        # Leg 0: IOC BUY at 100_000_000 for 5 units (will fully fill)
        # Leg 1: POST_ONLY BUY at 90_000_000 for 2 units (will rest)
        leg0 = BasketLeg(side="BUY", price=100_000_000, qty=5, flag="IOC")
        leg1 = BasketLeg(side="BUY", price=90_000_000, qty=2, flag="POST_ONLY")

        reps = engine.process(Event(kind="BASKET", account="A1", legs=(leg0, leg1)))
        assert Report.basket_committed() in reps
        assert any(r.kind == "FILL" for r in reps)
        assert any(r.kind == "ACCEPTED" and r.order_id == 3 for r in reps)

        violations = check_invariants(engine.state, 2)
        assert not violations

    def test_basket_rollback_on_failure(self):
        cfg = EngineConfig()
        accounts = {"A1": 10_000_000_000, "A2": 10_000_000_000, "LIQ": 10_000_000_000}
        engine = Engine(cfg, accounts, mark_price=100_000_000)

        # Resting SELL at 100_000_000
        engine.process(Event(kind="NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=5))

        h_before = engine.state_hash()

        # Basket where leg 0 would succeed (IOC buy 2 units), but leg 1 fails (POST_ONLY buy at 100M crosses)
        leg0 = BasketLeg(side="BUY", price=100_000_000, qty=2, flag="IOC")
        leg1 = BasketLeg(side="BUY", price=100_000_000, qty=2, flag="POST_ONLY")  # crosses resting sell at 100M

        reps = engine.process(Event(kind="BASKET", account="A1", legs=(leg0, leg1)))
        assert reps == [Report.basket_rolled_back(1)]  # 0-based index of failing leg

        # Complete state restored
        h_after = engine.state_hash()
        assert h_after == h_before
