"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.state import SessionState
from exchange_core.types import Event, Report


def _ensure_session(engine: "Engine", session_id: str) -> SessionState:  # type: ignore # noqa: F821
    """Return the session state, creating it on first use (R-S1)."""
    session = engine.state.sessions.get(session_id)
    if session is None:
        session = SessionState(epoch=0, next_seq=1, buffer={})
        engine.state.sessions[session_id] = session
    return session


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    if event.kind == "SESSION_RESET":
        session = _ensure_session(engine, event.session)
        session.epoch += 1
        session.next_seq = 1
        session.buffer.clear()
        return [Report.session_reset_done(event.session)]

    if event.kind != "FIX_MSG":
        return []

    session = _ensure_session(engine, event.session)

    # R-S2
    if event.epoch != session.epoch:
        return [Report.discarded("EPOCH")]

    # R-S3
    if event.seq < session.next_seq:
        if event.poss_dup:
            return [Report.discarded("DUPLICATE")]
        return [Report.discarded("SEQ_TOO_LOW")]

    # R-S5
    if event.seq > session.next_seq:
        if event.seq in session.buffer:
            return [Report.discarded("DUPLICATE_BUFFERED")]
        session.buffer[event.seq] = event
        return [Report.buffered()]

    # R-S4: event.seq == session.next_seq
    session.next_seq += 1
    reports: list[Report] = []
    if event.body is not None:
        reports.extend(engine.dispatch(event.body))

    # Drain consecutive buffered messages in ascending sequence order (R-S4, R-S9).
    while session.next_seq in session.buffer:
        buffered = session.buffer.pop(session.next_seq)
        session.next_seq += 1
        if buffered.body is not None:
            reports.extend(engine.dispatch(buffered.body))

    return reports
