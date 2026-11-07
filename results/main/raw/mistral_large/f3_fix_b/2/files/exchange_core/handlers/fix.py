"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.state import SessionState
from exchange_core.types import Event, Report


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    state = engine.state

    if event.kind == "SESSION_RESET":
        # R-S1: a session id not yet present is created on first use.
        if event.session not in state.sessions:
            state.sessions[event.session] = SessionState(epoch=0, next_seq=1, buffer={})
        sess = state.sessions[event.session]
        # R-S8: reset bumps the epoch, restarts the sequence, and clears the buffer.
        sess.epoch += 1
        sess.next_seq = 1
        sess.buffer.clear()
        return [Report.session_reset_done(event.session)]

    # FIX_MSG handling.
    # R-S1: a session id not yet present is created on first use.
    if event.session not in state.sessions:
        state.sessions[event.session] = SessionState(epoch=0, next_seq=1, buffer={})
    sess = state.sessions[event.session]

    # R-S2: reject messages from a different epoch.
    if event.epoch != sess.epoch:
        return [Report.discarded("EPOCH")]

    # R-S3: sequence number already consumed.
    if event.seq < sess.next_seq:
        if event.poss_dup:
            return [Report.discarded("DUPLICATE")]
        return [Report.discarded("SEQ_TOO_LOW")]

    # R-S5: sequence number ahead of the expected one -> buffer it.
    if event.seq > sess.next_seq:
        if event.seq in sess.buffer:
            return [Report.discarded("DUPLICATE_BUFFERED")]
        sess.buffer[event.seq] = event
        return [Report.buffered()]

    # R-S4: seq == next_seq -> accept, advance, and drain consecutive buffered messages.
    sess.next_seq += 1
    reports: list[Report] = []
    # R-S9: a None body carries no order event and adds no reports.
    if event.body is not None:
        reports.extend(engine.dispatch(event.body))
    while sess.next_seq in sess.buffer:
        buffered = sess.buffer.pop(sess.next_seq)
        sess.next_seq += 1
        if buffered.body is not None:
            reports.extend(engine.dispatch(buffered.body))
    return reports
