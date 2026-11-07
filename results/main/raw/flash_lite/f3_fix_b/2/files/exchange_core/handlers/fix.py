"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import SessionState


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    if event.kind == "SESSION_RESET":
        session_id = event.session
        if session_id not in engine.state.sessions:
            engine.state.sessions[session_id] = SessionState(epoch=0, next_seq=1, buffer={})
        
        session = engine.state.sessions[session_id]
        session.epoch += 1
        session.next_seq = 1
        session.buffer.clear()
        return [Report.session_reset_done(session_id)]

    # Rule R-S1: Initialize session if first use
    if event.session not in engine.state.sessions:
        engine.state.sessions[event.session] = SessionState(epoch=0, next_seq=1, buffer={})
    
    session = engine.state.sessions[event.session]
    
    # Rule R-S2: Reject epoch mismatch
    if event.epoch != session.epoch:
        return [Report.discarded("EPOCH")]
    
    # Rule R-S3: Check sequence vs next_seq
    if event.seq < session.next_seq:
        if event.poss_dup:
            return [Report.discarded("DUPLICATE")]
        else:
            return [Report.discarded("SEQ_TOO_LOW")]
            
    # Rule R-S5: Buffer future messages
    if event.seq > session.next_seq:
        if event.seq in session.buffer:
            return [Report.discarded("DUPLICATE_BUFFERED")]
        else:
            session.buffer[event.seq] = event
            return [Report.buffered()]
    
    # Rule R-S4 & R-S9: In-order processing and drainage
    reports = []
    
    # Process the current message
    if event.body is not None:
        reports.extend(engine.dispatch(event.body))
    session.next_seq += 1
    
    # Drain consecutive messages from buffer
    while session.next_seq in session.buffer:
        next_msg = session.buffer.pop(session.next_seq)
        if next_msg.body is not None:
            reports.extend(engine.dispatch(next_msg.body))
        session.next_seq += 1
        
    return reports
