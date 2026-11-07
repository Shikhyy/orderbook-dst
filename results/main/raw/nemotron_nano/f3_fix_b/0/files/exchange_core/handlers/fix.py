"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.types import Event, Report


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    # Ensure session exists
    sess = engine.state.sessions.setdefault(event.session, SessionState(epoch=0, next_seq=1, buffer={}))

    # R-S2: epoch mismatch
    if event.epoch != sess.epoch:
        return [Report.discarded("EPOCH")]

    # R-S3: seq < next_seq
    if event.seq < sess.next_seq:
        if event.poss_dup:
            return [Report.discarded("DUPLICATE")]
        else:
            return [Report.discarded("SEQ_TOO_LOW")]

    # R-S4: seq == next_seq
    if event.seq == sess.next_seq:
        reports = []
        # dispatch body if any
        if event.body is not None:
            reports = engine.dispatch(event.body)
        # accept and advance next_seq
        sess.next_seq += 1
        # drain buffered messages in order
        while sess.next_seq in sess.buffer:
            buf_msg = sess.buffer.pop(sess.next_seq)
            if buf_msg.body is not None:
                reports.extend(engine.dispatch(buf_msg.body))
            sess.next_seq += 1
        return reports

    # R-S5: seq > next_seq
    if event.seq > sess.next_seq:
        if event.seq in sess.buffer:
            return [Report.discarded("DUPLICATE_BUFFERED")]
        else:
            sess.buffer[event.seq] = event
            return [Report.buffered()]

    # R-S8: SESSION_RESET
    if event.kind == "SESSION_RESET":
        # Ensure session exists (already done above)
        sess.epoch += 1
        sess.next_seq = 1
        sess.buffer.clear()
        return [Report.session_reset_done(event.session)]

    # Unknown kind
    return []
