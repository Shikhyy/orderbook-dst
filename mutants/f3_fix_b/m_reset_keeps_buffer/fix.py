"""mutants/f3_fix_b/m_reset_keeps_buffer/fix.py
Mutant that preserves existing buffer across session resets.
"""
from exchange_core.rules.session_rule import on_message
from exchange_core.state import SessionState
from exchange_core.types import Event, Report


def handle_fix(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    state = engine.state

    if event.kind == "SESSION_RESET":
        session_id = event.session
        if session_id not in state.sessions:
            state.sessions[session_id] = SessionState(epoch=1, next_seq=1, buffer={})
        else:
            session = state.sessions[session_id]
            session.epoch += 1
            session.next_seq = 1
            # Mutant bug: fails to clear buffer on reset
        return [Report.session_reset_done(session_id)]

    session_id = event.session
    if session_id not in state.sessions:
        state.sessions[session_id] = SessionState(epoch=0, next_seq=1, buffer={})

    session = state.sessions[session_id]
    outcome = on_message(session, event)

    if outcome.reports:
        return outcome.reports

    all_reports: list[Report] = []
    for msg in outcome.to_process:
        if msg.body is not None:
            body_reports = engine.dispatch(msg.body)
            all_reports.extend(body_reports)

    return all_reports
