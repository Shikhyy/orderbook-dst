"""exchange_core/handlers/fix.py
Handle FIX_MSG and SESSION_RESET events.
Rules R-S1 to R-S9.
"""
from typing import Any

from exchange_core.rules.session_rule import on_message
from exchange_core.state import SessionState
from exchange_core.types import Event, Report


def handle_fix(engine: Any, event: Event) -> list[Report]:
    """Handle FIX sequence and session reset events.

    Rules R-S1 to R-S9.
    """
    if event.kind == "SESSION_RESET":
        session = engine.state.sessions.get(event.session)
        if session is None:
            session = SessionState(epoch=0, next_seq=1, buffer={})
            engine.state.sessions[event.session] = session
        session.epoch += 1
        session.next_seq = 1
        session.buffer.clear()
        return [Report.session_reset_done(event.session)]

    # FIX_MSG
    session = engine.state.sessions.get(event.session)
    if session is None:
        session = SessionState(epoch=0, next_seq=1, buffer={})
        engine.state.sessions[event.session] = session

    outcome = on_message(session, event)
    reports: list[Report] = list(outcome.reports)
    for msg in outcome.to_process:
        body = getattr(msg, "body", None)
        if body is not None:
            reports.extend(engine.dispatch(body))
    return reports
