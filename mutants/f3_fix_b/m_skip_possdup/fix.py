"""mutants/f3_fix_b/m_skip_possdup/fix.py
Mutant that discards all poss_dup messages.
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
            session.buffer.clear()
        return [Report.session_reset_done(session_id)]

    session_id = event.session
    if session_id not in state.sessions:
        state.sessions[session_id] = SessionState(epoch=0, next_seq=1, buffer={})

    # Mutant bug: discards any poss_dup message unconditionally
    if event.poss_dup:
        return [Report.discarded("DUPLICATE")]

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
