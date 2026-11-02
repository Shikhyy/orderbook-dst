"""tasks/f3_fix_a/public_tests/test_f3_fix_a.py
Public tests for task f3_fix_a.
"""
from exchange_core.rules.session_rule import on_message
from exchange_core.state import SessionState
from exchange_core.types import Event, Report


def test_in_order_message():
    session = SessionState(epoch=1, next_seq=1, buffer={})
    msg = Event(kind="FIX_MSG", session="S1", epoch=1, seq=1, poss_dup=False)
    out = on_message(session, msg)
    assert out.to_process == [msg]
    assert out.reports == []
    assert session.next_seq == 2


def test_gap_then_fill():
    session = SessionState(epoch=1, next_seq=1, buffer={})
    msg2 = Event(kind="FIX_MSG", session="S1", epoch=1, seq=2, poss_dup=False)
    out2 = on_message(session, msg2)
    assert out2.to_process == []
    assert out2.reports == [Report.buffered()]
    assert session.next_seq == 1
    assert 2 in session.buffer

    msg1 = Event(kind="FIX_MSG", session="S1", epoch=1, seq=1, poss_dup=False)
    out1 = on_message(session, msg1)
    # Drain order: msg1 followed by buffered msg2
    assert out1.to_process == [msg1, msg2]
    assert out1.reports == []
    assert session.next_seq == 3
    assert len(session.buffer) == 0


def test_duplicate_with_poss_dup_true():
    session = SessionState(epoch=1, next_seq=3, buffer={})
    msg = Event(kind="FIX_MSG", session="S1", epoch=1, seq=2, poss_dup=True)
    out = on_message(session, msg)
    assert out.to_process == []
    assert out.reports == [Report.discarded("DUPLICATE")]
    assert session.next_seq == 3


def test_duplicate_with_poss_dup_false():
    session = SessionState(epoch=1, next_seq=3, buffer={})
    msg = Event(kind="FIX_MSG", session="S1", epoch=1, seq=2, poss_dup=False)
    out = on_message(session, msg)
    assert out.to_process == []
    assert out.reports == [Report.discarded("SEQ_TOO_LOW")]
    assert session.next_seq == 3


def test_epoch_mismatch():
    session = SessionState(epoch=2, next_seq=1, buffer={})
    msg = Event(kind="FIX_MSG", session="S1", epoch=1, seq=1, poss_dup=False)
    out = on_message(session, msg)
    assert out.to_process == []
    assert out.reports == [Report.discarded("EPOCH")]
    assert session.next_seq == 1


def test_buffer_drain_order():
    session = SessionState(epoch=1, next_seq=1, buffer={})
    # Arrive out of order: 4, 3, 2
    msg4 = Event(kind="FIX_MSG", session="S1", epoch=1, seq=4, poss_dup=False)
    msg3 = Event(kind="FIX_MSG", session="S1", epoch=1, seq=3, poss_dup=False)
    msg2 = Event(kind="FIX_MSG", session="S1", epoch=1, seq=2, poss_dup=False)
    on_message(session, msg4)
    on_message(session, msg3)
    on_message(session, msg2)
    assert session.next_seq == 1
    assert len(session.buffer) == 3

    # Now seq 1 arrives: should drain 1, 2, 3, 4
    msg1 = Event(kind="FIX_MSG", session="S1", epoch=1, seq=1, poss_dup=False)
    out = on_message(session, msg1)
    assert out.to_process == [msg1, msg2, msg3, msg4]
    assert session.next_seq == 5
    assert len(session.buffer) == 0


def test_duplicate_in_buffer():
    session = SessionState(epoch=1, next_seq=1, buffer={})
    msg3_a = Event(kind="FIX_MSG", session="S1", epoch=1, seq=3, poss_dup=False)
    out_a = on_message(session, msg3_a)
    assert out_a.reports == [Report.buffered()]

    msg3_b = Event(kind="FIX_MSG", session="S1", epoch=1, seq=3, poss_dup=True)
    out_b = on_message(session, msg3_b)
    assert out_b.reports == [Report.discarded("DUPLICATE_BUFFERED")]
    assert session.buffer[3] == msg3_a


def test_poss_dup_true_with_seq_equals_next_seq():
    session = SessionState(epoch=1, next_seq=2, buffer={})
    # Rule R-S4: if seq == next_seq, accepted even if poss_dup == True
    msg = Event(kind="FIX_MSG", session="S1", epoch=1, seq=2, poss_dup=True)
    out = on_message(session, msg)
    assert out.to_process == [msg]
    assert out.reports == []
    assert session.next_seq == 3


def test_two_gaps():
    session = SessionState(epoch=1, next_seq=1, buffer={})
    # Gap at 1: arrive 2, then 4
    msg2 = Event(kind="FIX_MSG", session="S1", epoch=1, seq=2, poss_dup=False)
    msg4 = Event(kind="FIX_MSG", session="S1", epoch=1, seq=4, poss_dup=False)
    on_message(session, msg2)
    on_message(session, msg4)

    # 1 arrives: drains 1 and 2, but leaves 4 in buffer
    msg1 = Event(kind="FIX_MSG", session="S1", epoch=1, seq=1, poss_dup=False)
    out = on_message(session, msg1)
    assert out.to_process == [msg1, msg2]
    assert session.next_seq == 3
    assert list(session.buffer.keys()) == [4]
