"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import SessionState

def handle_fix(engine: "Engine", event: Event) -> list[Report]:
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    reports = []

    if event.kind == "SESSION_RESET":
        # Rule R-S8: Handle SESSION_RESET
        session = engine.state.sessions.get(event.session, SessionState(epoch=0, next_seq=1, buffer={}))
        session.epoch += 1
        session.next_seq = 1
        session.buffer.clear()
        reports.append(Report.session_reset_done(event.session))
        engine.state.sessions[event.session] = session
        return reports

    if event.kind != "FIX_MSG":
        return reports

    # Rule R-S1: Initialize session if not exists
    session = engine.state.sessions.get(event.session, SessionState(epoch=0, next_seq=1, buffer={}))

    # Rule R-S2: Check epoch mismatch
    if event.epoch != session.epoch:
        reports.append(Report.discarded("EPOCH"))
        return reports

    # Rule R-S3: Handle seq < next_seq
    if event.seq < session.next_seq:
        if event.poss_dup:
            reports.append(Report.discarded("DUPLICATE"))
        else:
            reports.append(Report.discarded("SEQ_TOO_LOW"))
        return reports

    # Rule R-S4: Handle seq == next_seq
    if event.seq == session.next_seq:
        # Accept the message
        if event.body is not None:
            reports.extend(engine.dispatch(event.body))

        # Increment next_seq
        session.next_seq += 1

        # Drain buffered messages in ascending order
        while session.next_seq in session.buffer:
            buffered_msg = session.buffer[session.next_seq]
            if buffered_msg.body is not None:
                reports.extend(engine.dispatch(buffered_msg.body))
            session.next_seq += 1

        # Update session state
        engine.state.sessions[event.session] = session
        return reports

    # Rule R-S5: Handle seq > next_seq
    if event.seq in session.buffer:
        reports.append(Report.discarded("DUPLICATE_BUFFERED"))
    else:
        session.buffer[event.seq] = event
        reports.append(Report.buffered())

    # Update session state
    engine.state.sessions[event.session] = session
    return reports
