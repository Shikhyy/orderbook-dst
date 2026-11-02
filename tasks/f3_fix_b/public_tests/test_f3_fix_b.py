"""tasks/f3_fix_b/public_tests/test_f3_fix_b.py
Public tests for task f3_fix_b.
"""
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.handlers.fix import handle_fix
from exchange_core.types import Event, Report


def _make_engine():
    cfg = EngineConfig()
    accounts = {"A1": 100_000_000_000, "A2": 100_000_000_000}
    return Engine(cfg, accounts, 100_000_000)


def test_in_order_dispatch():
    eng = _make_engine()
    body = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10)
    ev = Event(kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=False, body=body)
    reps = handle_fix(eng, ev)
    assert len(reps) == 1
    assert reps[0].kind == "ACCEPTED"
    assert eng.state.sessions["S1"].next_seq == 2


def test_gap_buffering():
    eng = _make_engine()
    body = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10)
    ev = Event(kind="FIX_MSG", session="S1", epoch=0, seq=2, poss_dup=False, body=body)
    reps = handle_fix(eng, ev)
    assert reps == [Report.buffered()]
    assert eng.state.sessions["S1"].next_seq == 1
    assert 2 in eng.state.sessions["S1"].buffer


def test_gap_fill_and_drain():
    eng = _make_engine()
    body2 = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=5)
    ev2 = Event(kind="FIX_MSG", session="S1", epoch=0, seq=2, poss_dup=False, body=body2)
    handle_fix(eng, ev2)

    body1 = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10)
    ev1 = Event(kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=False, body=body1)
    reps = handle_fix(eng, ev1)
    # Both bodies dispatched: order 1 accepted, then order 2 accepted
    assert len(reps) == 2
    assert reps[0].kind == "ACCEPTED"
    assert reps[1].kind == "ACCEPTED"
    assert eng.state.sessions["S1"].next_seq == 3
    assert len(eng.state.sessions["S1"].buffer) == 0


def test_duplicate_poss_dup_true():
    eng = _make_engine()
    ev1 = Event(
        kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=False,
        body=Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10)
    )
    handle_fix(eng, ev1)

    ev_dup = Event(kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=True, body=None)
    reps = handle_fix(eng, ev_dup)
    assert reps == [Report.discarded("DUPLICATE")]


def test_duplicate_poss_dup_false():
    eng = _make_engine()
    ev1 = Event(
        kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=False,
        body=Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10)
    )
    handle_fix(eng, ev1)

    ev_dup = Event(kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=False, body=None)
    reps = handle_fix(eng, ev_dup)
    assert reps == [Report.discarded("SEQ_TOO_LOW")]


def test_epoch_mismatch():
    eng = _make_engine()
    # Initialize session at epoch 0
    ev1 = Event(kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=False, body=None)
    handle_fix(eng, ev1)

    # Message with wrong epoch
    ev_bad = Event(kind="FIX_MSG", session="S1", epoch=5, seq=2, poss_dup=False, body=None)
    reps = handle_fix(eng, ev_bad)
    assert reps == [Report.discarded("EPOCH")]


def test_duplicate_buffered():
    eng = _make_engine()
    ev3_a = Event(kind="FIX_MSG", session="S1", epoch=0, seq=3, poss_dup=False, body=None)
    reps_a = handle_fix(eng, ev3_a)
    assert reps_a == [Report.buffered()]

    ev3_b = Event(kind="FIX_MSG", session="S1", epoch=0, seq=3, poss_dup=True, body=None)
    reps_b = handle_fix(eng, ev3_b)
    assert reps_b == [Report.discarded("DUPLICATE_BUFFERED")]


def test_poss_dup_true_in_sequence():
    eng = _make_engine()
    body = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10)
    ev = Event(kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=True, body=body)
    reps = handle_fix(eng, ev)
    assert len(reps) == 1
    assert reps[0].kind == "ACCEPTED"
    assert eng.state.sessions["S1"].next_seq == 2


def test_session_reset():
    eng = _make_engine()
    # Create buffered message at seq 3
    ev3 = Event(kind="FIX_MSG", session="S1", epoch=0, seq=3, poss_dup=False, body=None)
    handle_fix(eng, ev3)
    assert len(eng.state.sessions["S1"].buffer) == 1

    # Reset
    rst = Event(kind="SESSION_RESET", session="S1")
    reps = handle_fix(eng, rst)
    assert reps == [Report.session_reset_done("S1")]

    sess = eng.state.sessions["S1"]
    assert sess.epoch == 1
    assert sess.next_seq == 1
    assert len(sess.buffer) == 0
