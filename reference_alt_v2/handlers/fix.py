"""FIX session sequencing handler.

Rules:
- R-S1 to R-S9: Session management, message validation, sequencing, buffering, draining, reset.
"""
from typing import Any

from exchange_core.state import SessionState
from exchange_core.types import Event, Report

try:
    from exchange_core.rules.session_rule import on_message
except ImportError:
    from reference_alt_v2.rules.session_rule import on_message


def handle_fix(engine: Any, event: Event) -> list[Report]:
    """Handle FIX_MSG or SESSION_RESET events.

    Rules R-S1 to R-S9:
    - SESSION_RESET:
      Adds 1 to epoch, sets next_seq to 1, empties buffer, reports SESSION_RESET_DONE.
    - FIX_MSG:
      Delegates sequence validation to on_message rule.
      Processes admitted bodies via engine.process.
      Returns discarded/buffered reports or accumulated body execution reports.
    """
    session_id = event.session
    if session_id not in engine.state.sessions:
        engine.state.sessions[session_id] = SessionState(epoch=0, next_seq=1, buffer={})
    session = engine.state.sessions[session_id]

    if event.kind == "SESSION_RESET":
        session.epoch += 1
        session.next_seq = 1
        session.buffer.clear()
        return [Report.session_reset_done(session_id)]

    # FIX_MSG
    outcome = on_message(session, event)
    reports: list[Report] = list(outcome.reports)

    for msg in outcome.to_process:
        if msg.body is not None:
            body_reports = engine.process(msg.body)
            reports.extend(body_reports)

    return reports
