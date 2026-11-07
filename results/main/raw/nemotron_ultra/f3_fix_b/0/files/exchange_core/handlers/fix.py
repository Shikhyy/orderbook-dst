"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import SessionState


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    session_id = event.session

    # R-S1: Create session if not exists (for both FIX_MSG and SESSION_RESET)
    if session_id not in engine.state.sessions:
        engine.state.sessions[session_id] = SessionState(epoch=0, next_seq=1, buffer={})

    session = engine.state.sessions[session_id]

    if event.kind == "SESSION_RESET":
        # R-S8
        session.epoch += 1
        session.next_seq = 1
        session.buffer.clear()
        return [Report.session_reset_done(session_id)]

    elif event.kind == "FIX_MSG":
        # R-S2: Check epoch
        if event.epoch != session.epoch:
            return [Report.discarded("EPOCH")]

        seq = event.seq
        next_seq = session.next_seq

        if seq < next_seq:
            # R-S3
            if event.poss_dup:
                return [Report.discarded("DUPLICATE")]
            else:
                return [Report.discarded("SEQ_TOO_LOW")]

        elif seq == next_seq:
            # R-S4
            reports = []

            # Process current message
            if event.body is not None:
                body_reports = engine.dispatch(event.body)
                reports.extend(body_reports)

            session.next_seq += 1

            # Drain buffer in ascending sequence order
            while session.next_seq in session.buffer:
                buffered_msg = session.buffer.pop(session.next_seq)
                if buffered_msg.body is not None:
                    body_reports = engine.dispatch(buffered_msg.body)
                    reports.extend(body_reports)
                session.next_seq += 1

            return reports

        else:  # seq > next_seq
            # R-S5
            if seq in session.buffer:
                return [Report.discarded("DUPLICATE_BUFFERED")]
            else:
                session.buffer[seq] = event
                return [Report.buffered()]

    else:
        # Unknown event kind
        return []
