"""exchange_core/handlers/fix.py
Handle FIX_MSG and SESSION_RESET events.
Rules R-S1 to R-S9. Target for task f3_fix_b.
"""
from exchange_core.rules.session_rule import on_message
from exchange_core.state import SessionState
from exchange_core.types import Event, Report


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Handle FIX session events (FIX_MSG and SESSION_RESET).

    Rules R-S1 to R-S9.
    """
    state = engine.state

    # Rule R-S8: SESSION_RESET
    if event.kind == "SESSION_RESET":
        session_id = event.session
        if session_id not in state.sessions:
            state.sessions[session_id] = SessionState(epoch=0, next_seq=1, buffer={})
        session = state.sessions[session_id]
        session.epoch += 1
        session.next_seq = 1
        session.buffer.clear()
        return [Report.session_reset_done(session_id)]

    # Rule R-S1 to R-S7: FIX_MSG
    session_id = event.session
    if session_id not in state.sessions:
        state.sessions[session_id] = SessionState(epoch=0, next_seq=1, buffer={})

    session = state.sessions[session_id]
    outcome = on_message(session, event)

    # If message was buffered or discarded, return session report
    if outcome.reports:
        return outcome.reports

    # Rule R-S9: reports for processed message body, followed by drained bodies
    all_reports: list[Report] = []
    for msg in outcome.to_process:
        if msg.body is not None:
            body_reports = engine.dispatch(msg.body)
            all_reports.extend(body_reports)

    return all_reports
