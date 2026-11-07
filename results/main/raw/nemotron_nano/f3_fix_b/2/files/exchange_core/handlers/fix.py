"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import SessionState


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    # Handle SESSION_RESET first
    if event.kind == "SESSION_RESET":
        # Ensure session exists
        sess = engine.state.sessions.get(event.session)
        if sess is None:
            sess = SessionState(epoch=0, next_seq=1, buffer={})
            engine.state.sessions[event.session] = sess
        # Apply reset rules
        sess.epoch += 1
        sess.next_seq = 1
        sess.buffer.clear()
        return [Report.session_reset_done(event.session)]

    # Ensure session state exists for FIX_MSG
    sess = engine.state.sessions.get(event.session)
    if sess is None:
        sess = SessionState(epoch=0, next_seq=1, buffer={})
        engine.state.sessions[event.session] = sess

    # Epoch mismatch
    if event.epoch != sess.epoch:
        return [Report.discarded("EPOCH")]

    # Sequence handling
    if event.seq < sess.next_seq:
        if event.poss_dup:
            return [Report.discarded("DUPLICATE")]
        else:
            return [Report.discarded("SEQ_TOO_LOW")]
    elif event.seq == sess.next_seq:
        # Accept the message
        old_next = sess.next_seq
        sess.next_seq = old_next + 1
        reports = []
        # Dispatch current message body if present
        if event.body is not None:
            reports.extend(engine.dispatch(event.body))
        # Drain consecutive buffered messages
        while sess.next_seq in sess.buffer:
            buf_msg = sess.buffer.pop(sess.next_seq)
            sess.next_seq += 1
            if buf_msg.body is not None:
                reports.extend(engine.dispatch(buf_msg.body))
        return reports
    else:  # event.seq > sess.next_seq
        if event.seq in sess.buffer:
            return [Report.discarded("DUPLICATE_BUFFERED")]
        else:
            sess.buffer[event.seq] = event
            return [Report.buffered()]
