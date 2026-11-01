# tests/test_core_types.py
# Tests for EngineConfig, types, EngineState, snapshot/restore, and canonical state hash.
# Written before implementation (TDD).

from exchange_core.canonical import canonical_json, canonical_state_hash
from exchange_core.config import EngineConfig
from exchange_core.state import Account, EngineState, SessionState
from exchange_core.types import (
    Event,
    Order,
    Report,
)


class TestEngineConfig:
    """Config constants defined in docs/04_RULEBOOK.md section 1."""

    def test_default_values(self):
        cfg = EngineConfig()
        assert cfg.tick == 10_000
        assert cfg.margin_bps_default == 2_000
        assert cfg.maint_bps == 500
        assert cfg.ppm == 1_000_000
        assert cfg.taker_ppm_t0 == 2_750
        assert cfg.taker_ppm_t1 == 1_850
        assert cfg.maker_rebate_ppm == 250
        assert cfg.tier_threshold == 5_000_010_000

    def test_uppercase_aliases(self):
        cfg = EngineConfig()
        assert cfg.TICK == 10_000
        assert cfg.MARGIN_BPS_DEFAULT == 2_000
        assert cfg.MAINT_BPS == 500
        assert cfg.PPM == 1_000_000
        assert cfg.TAKER_PPM_T0 == 2_750
        assert cfg.TAKER_PPM_T1 == 1_850
        assert cfg.MAKER_REBATE_PPM == 250
        assert cfg.TIER_THRESHOLD == 5_000_010_000

    def test_custom_values(self):
        cfg = EngineConfig(tick=5_000, margin_bps_default=1_000)
        assert cfg.tick == 5_000
        assert cfg.margin_bps_default == 1_000


class TestTypes:
    """Core domain types."""

    def test_order_leaves(self):
        order = Order(
            order_id=1,
            account="A1",
            side="BUY",
            price=100_000_000,
            qty=10,
            cum_qty=4,
            prio_seq=1,
            margin_bps=2_000,
            lock=120_000_000,
            flag="NONE",
        )
        assert order.leaves == 6

    def test_event_creation(self):
        ev = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10)
        assert ev.kind == "NEW_LIMIT"
        assert ev.account == "A1"
        assert ev.side == "BUY"
        assert ev.price == 100_000_000
        assert ev.qty == 10

    def test_report_creation(self):
        rep = Report(kind="ACCEPTED", order_id=42)
        assert rep.kind == "ACCEPTED"
        assert rep.order_id == 42


class TestStateAndSnapshot:
    """EngineState, snapshot, restore, and canonical hash."""

    def _sample_state(self) -> EngineState:
        acc1 = Account(free_cash=1_000_000_000, locked_margin=200_000_000, position=0, volume=0)
        acc2 = Account(free_cash=2_000_000_000, locked_margin=0, position=0, volume=0)
        order1 = Order(
            order_id=1,
            account="A1",
            side="BUY",
            price=100_000_000,
            qty=10,
            cum_qty=0,
            prio_seq=1,
            margin_bps=2_000,
            lock=200_000_000,
            flag="NONE",
        )
        session = SessionState(epoch=0, next_seq=1, buffer={})
        return EngineState(
            accounts={"A1": acc1, "A2": acc2},
            orders={1: order1},
            fee_vault=0,
            next_order_id=2,
            next_prio_seq=2,
            margin_bps=2_000,
            mark_price=100_000_000,
            sessions={"S1": session},
            initial_total=3_200_000_000,
        )

    def test_snapshot_restore_identity(self):
        """Snapshot law: restore(snapshot(s)) has the exact same hash as s."""
        state = self._sample_state()
        h_before = canonical_state_hash(state)
        snap = state.snapshot()

        # Mutate the live state
        state.accounts["A1"].free_cash += 500
        state.orders[1].cum_qty += 1
        state.fee_vault += 10
        state.next_order_id += 5
        h_mutated = canonical_state_hash(state)
        assert h_mutated != h_before

        # Restore from snapshot
        state.restore(snap)
        h_after = canonical_state_hash(state)
        assert h_after == h_before

    def test_canonical_hash_key_order_independence(self):
        """Account insertion order or order insertion order does not change hash."""
        s1 = self._sample_state()
        # s2 has accounts inserted in opposite order
        s2 = self._sample_state()
        s2.accounts = {"A2": s2.accounts["A2"], "A1": s2.accounts["A1"]}

        assert canonical_state_hash(s1) == canonical_state_hash(s2)
        assert canonical_json(s1) == canonical_json(s2)
