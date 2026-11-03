"""tests/test_coverage_edge_cases.py
Edge-case coverage tests for:
1. canonical.py: State hashing with non-empty FIX buffer and dict conversions (lines 31-38).
2. ledger.py: pay_fee, pay_rebate, and add_volume helper functions (lines 45-60).
3. handlers/fix.py: Unknown session auto-initialization starting at epoch 0 per Rule R-S2.
"""

from exchange_core.canonical import _msg_to_dict, canonical_state_hash
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.ledger import add_volume, pay_fee, pay_rebate
from exchange_core.state import SessionState
from exchange_core.types import Event


def test_canonical_hash_non_empty_buffer_twice() -> None:
    """Hash an EngineState with a non-empty FIX message buffer twice.
    Verifies that canonical_state_hash is strictly deterministic and covers _msg_to_dict.
    """
    engine = Engine(EngineConfig(), accounts={"A1": 1_000_000_000}, mark_price=100_000_000)
    state = engine.state

    body_event = Event(
        kind="NEW_LIMIT",
        account="A1",
        side="BUY",
        price=100_000_000,
        qty=10,
        flag="LIMIT",
    )
    fix_msg = Event(
        kind="FIX_MSG",
        session="S1",
        epoch=0,
        seq=5,
        poss_dup=False,
        body=body_event,
    )
    state.sessions["S1"] = SessionState(
        epoch=0,
        next_seq=1,
        buffer={5: fix_msg},
    )

    hash1 = canonical_state_hash(state)
    hash2 = canonical_state_hash(state)

    assert hash1 == hash2
    assert isinstance(hash1, str)
    assert len(hash1) == 64

    # Direct helper verification for lines 31-38 of canonical.py
    assert _msg_to_dict(None) == {}
    raw_dict = {"kind": "TEST", "body": {"inner": 123}}
    assert _msg_to_dict(raw_dict) == raw_dict


def test_ledger_pay_fee_pay_rebate_add_volume() -> None:
    """Verify ledger helper functions pay_fee, pay_rebate, and add_volume."""
    engine = Engine(EngineConfig(), accounts={"A1": 100_000_000}, mark_price=100_000_000)
    state = engine.state
    state.accounts["A1"].volume = 50_000_000
    state.fee_vault = 10_000_000

    # 1. pay_fee
    pay_fee(state, "A1", 5_000_000)
    assert state.accounts["A1"].free_cash == 95_000_000
    assert state.fee_vault == 15_000_000

    # 2. pay_rebate
    pay_rebate(state, "A1", 2_000_000)
    assert state.accounts["A1"].free_cash == 97_000_000
    assert state.fee_vault == 13_000_000

    # 3. add_volume
    add_volume(state, "A1", 25_000_000)
    assert state.accounts["A1"].volume == 75_000_000


def test_unknown_session_starts_at_epoch_zero() -> None:
    """Verify that an unknown session in handlers/fix.py starts at epoch 0 per Rule R-S2."""
    engine = Engine(EngineConfig(), accounts={"A1": 1_000_000_000}, mark_price=100_000_000)
    state = engine.state
    assert "S_UNKNOWN" not in state.sessions

    # Message sent to unknown session
    msg = Event(
        kind="FIX_MSG",
        session="S_UNKNOWN",
        epoch=0,
        seq=2,  # out of order -> should buffer
        poss_dup=False,
        body=Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=1),
    )
    reports = engine.dispatch(msg)

    assert "S_UNKNOWN" in state.sessions
    sess = state.sessions["S_UNKNOWN"]
    # Per R-S2: session epoch starts at 0, next_seq at 1
    assert sess.epoch == 0
    assert sess.next_seq == 1
    assert 2 in sess.buffer
    assert any(r.kind == "BUFFERED" for r in reports)

    # Session reset on another new session: should start at 0, increment to 1 per R-S8
    assert "S_RESET_NEW" not in state.sessions
    reset_event = Event(kind="SESSION_RESET", session="S_RESET_NEW")
    reset_reports = engine.dispatch(reset_event)

    assert "S_RESET_NEW" in state.sessions
    reset_sess = state.sessions["S_RESET_NEW"]
    assert reset_sess.epoch == 1
    assert reset_sess.next_seq == 1
    assert any(r.kind == "SESSION_RESET_DONE" for r in reset_reports)


def test_grader_tier2_expected_fee_vault_check() -> None:
    """Verify that grade_tier2 checks expected_fee_vault and fails if fee_vault is wrong."""
    from graders.dst_grader import _load_task_metadata, grade_tier2

    meta = _load_task_metadata("f4_waterfall_b")

    # Baseline Engine: fee_vault is correct, tier 2 score is 1.0
    t2_good, err_good = grade_tier2("f4_waterfall_b", Engine, meta)
    assert err_good is None
    assert t2_good == 1.0

    # Engine subclass that corrupts fee_vault
    class BadFeeVaultEngine(Engine):
        def process(self, event: Event):
            reps = super().process(event)
            self.state.fee_vault = 999_999_999
            return reps

    t2_bad, err_bad = grade_tier2("f4_waterfall_b", BadFeeVaultEngine, meta)
    assert err_bad is None
    assert t2_bad < 1.0
