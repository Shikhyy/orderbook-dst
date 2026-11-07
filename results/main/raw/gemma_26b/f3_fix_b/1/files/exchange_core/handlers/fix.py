"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import SessionState


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    session_id = event.session
    if session_id not in engine.state.sessions:
        engine.state.sessions[session_id] = SessionState(epoch=0, next_seq=1, buffer={})

    session = engine.state.sessions[session_id]

    if event.kind == "SESSION_RESET":
        session.epoch += 1
        session.next_seq = 1
        session.buffer.clear()
        return [Report.session_reset_done(session_id)]

    if event.kind != "FIX_MSG":
        # Technically not defined by rules, but for robustness:
        return []

    # R-S2: Epoch check
    if event.epoch != session.epoch:
        return [Report.discarded("EPOCH")]

    seq = event.seq

    # R-S3: Sequence too low
    if seq < session.next_seq:
        if event.poss_dup:
            return [Report.discarded("DUPLICATE")]
        else:
            return [Report.discarded("SEQ_TOO_LOW")]

    # R-S4: Sequence match
    if seq == session.next_seq:
        reports = []
        # Process the current message
        if event.body is not None:
            reports.extend(engine.dispatch(event.body))
        session.next_seq += 1

        # Drain buffer
        while session.next_seq in session.buffer:
            buffered_msg = session.buffer.pop(session.next_seq)
            if buffered_msg.body is not None:
                reports.extend(engine.dispatch(buffered_msg.body))
            session.next_seq += 1
        
        return reports

    # R-S5: Sequence gap
    if seq > session.next_seq:
        if seq in session.buffer:
            return [Report.discarded("DUPLICATE_BUFFERED")]
        else:
            session.buffer[seq] = event
            return [Report.buffered()]

    return []
