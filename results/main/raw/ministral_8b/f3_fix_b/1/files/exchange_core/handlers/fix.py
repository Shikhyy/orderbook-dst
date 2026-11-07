"""exchange_core/handlers/fix.py
Handler for FIX session messages and session reset.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.state import SessionState
from exchange_core.types import Event, Report

def handle_fix(engine: "Engine", event: Event) -> list[Report]:
    """Process FIX_MSG and SESSION_RESET events according to rules R-S1 to R-S9."""
    reports = []
    session = event.session

    # Initialize session if not exists (R-S1)
    if session not in engine.state.sessions:
        engine.state.sessions[session] = SessionState(epoch=0, next_seq=1, buffer={})

    sess = engine.state.sessions[session]

    if event.kind == "SESSION_RESET":
        # Handle SESSION_RESET (R-S8)
        sess.epoch += 1
        sess.next_seq = 1
        sess.buffer.clear()
        reports.append(Report.session_reset_done(session))
    elif event.kind == "FIX_MSG":
        # Handle FIX_MSG (R-S2 to R-S5, R-S9)
        if event.epoch != sess.epoch:
            reports.append(Report.discarded("EPOCH"))
        else:
            seq = event.seq
            poss_dup = event.poss_dup
            body = event.body

            if seq < sess.next_seq:
                if poss_dup:
                    reports.append(Report.discarded("DUPLICATE"))
                else:
                    reports.append(Report.discarded("SEQ_TOO_LOW"))
            elif seq == sess.next_seq:
                # Accept message (R-S4)
                reports.extend(engine.dispatch(body) if body else [])
                sess.next_seq += 1

                # Drain buffered messages (R-S4)
                while seq in sess.buffer:
                    buffered_msg = sess.buffer.pop(seq)
                    if buffered_msg.body:
                        reports.extend(engine.dispatch(buffered_msg.body))
                    sess.next_seq += 1
                    seq += 1
            else:  # seq > sess.next_seq
                if seq in sess.buffer:
                    reports.append(Report.discarded("DUPLICATE_BUFFERED"))
                else:
                    sess.buffer[seq] = event
                    reports.append(Report.buffered())

    return reports
