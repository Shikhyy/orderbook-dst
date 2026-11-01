# tests/test_invariants_sensitivity.py
# Verification of invariant detection sensitivity (Requirement V8, INV-01 to INV-04).
# Proves that I1, I2, and I3 correctly detect violations when faults are introduced.

from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.invariants import check_i1, check_i2, check_i3
from exchange_core.types import Event, Order


class TestInvariantSensitivity:
    """Deliberately introduce faults and confirm invariant checker catches them."""

    def _basic_engine(self) -> Engine:
        cfg = EngineConfig()
        accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
        return Engine(cfg, accounts, mark_price=100_000_000)

    def test_i1_detects_money_creation(self):
        engine = self._basic_engine()
        # Create unbacked money in A1
        engine.state.accounts["A1"].free_cash += 100_000

        violations = check_i1(engine.state, 1)
        assert len(violations) == 1
        assert violations[0].invariant == "I1"
        assert violations[0].plain_name == "No money created or destroyed"

    def test_i1_detects_money_destruction(self):
        engine = self._basic_engine()
        # Destroy money
        engine.state.fee_vault -= 50_000

        violations = check_i1(engine.state, 1)
        assert len(violations) == 1
        assert violations[0].invariant == "I1"

    def test_i2_detects_order_lock_mismatch(self):
        engine = self._basic_engine()
        engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))

        # Tamper with order lock without changing account locked_margin
        engine.state.orders[1].lock += 1_000

        violations = check_i2(engine.state, 1)
        assert any(v.invariant == "I2" and "order 1 lock" in v.message for v in violations)

    def test_i2_detects_account_locked_margin_mismatch(self):
        engine = self._basic_engine()
        engine.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))

        # Tamper with account locked_margin
        engine.state.accounts["A1"].locked_margin += 5_000

        violations = check_i2(engine.state, 1)
        assert any(v.invariant == "I2" and "account A1" in v.message for v in violations)

    def test_i3_detects_crossed_book(self):
        engine = self._basic_engine()
        # Manually insert crossed orders into state
        engine.state.orders[1] = Order(
            order_id=1, account="A1", side="BUY", price=101_000_000,
            qty=1, cum_qty=0, prio_seq=1, margin_bps=2_000, lock=20_200_000, flag="NONE"
        )
        engine.state.orders[2] = Order(
            order_id=2, account="A2", side="SELL", price=100_000_000,
            qty=1, cum_qty=0, prio_seq=2, margin_bps=2_000, lock=20_000_000, flag="NONE"
        )

        violations = check_i3(engine.state, 1)
        assert any(v.invariant == "I3" and "crossed book" in v.message for v in violations)

    def test_i3_detects_zero_leaves_resting_order(self):
        engine = self._basic_engine()
        engine.state.orders[1] = Order(
            order_id=1, account="A1", side="BUY", price=100_000_000,
            qty=5, cum_qty=5, prio_seq=1, margin_bps=2_000, lock=0, flag="NONE"
        )

        violations = check_i3(engine.state, 1)
        assert any(v.invariant == "I3" and "leaves 0" in v.message for v in violations)

    def test_i3_detects_invalid_price(self):
        engine = self._basic_engine()
        engine.state.orders[1] = Order(
            order_id=1, account="A1", side="BUY", price=100_005,  # not multiple of 10_000
            qty=5, cum_qty=0, prio_seq=1, margin_bps=2_000, lock=100_005, flag="NONE"
        )

        violations = check_i3(engine.state, 1)
        assert any(v.invariant == "I3" and "invalid price" in v.message for v in violations)

    def test_i3_detects_duplicate_prio_seq(self):
        engine = self._basic_engine()
        engine.state.orders[1] = Order(
            order_id=1, account="A1", side="BUY", price=100_000_000,
            qty=5, cum_qty=0, prio_seq=1, margin_bps=2_000, lock=100_000_000, flag="NONE"
        )
        engine.state.orders[2] = Order(
            order_id=2, account="A2", side="BUY", price=90_000_000,
            qty=5, cum_qty=0, prio_seq=1, margin_bps=2_000, lock=90_000_000, flag="NONE"
        )

        violations = check_i3(engine.state, 1)
        assert any(v.invariant == "I3" and "duplicate prio_seq" in v.message for v in violations)
