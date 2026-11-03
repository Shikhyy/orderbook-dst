"""FIX session sequencing handler (Task f3_fix_b).

Rules:
- R-S1 to R-S9: Session management, message validation, sequencing, buffering, draining, reset.
"""
from typing import Any

"""reference/f3_fix_a/session_rule.py
Reference solution for task f3_fix_a.
Rules R-S1 to R-S7.
"""
from exchange_core.state import SessionState
from exchange_core.types import FixMsg, Report, SessionOutcome


def on_message(session: SessionState, msg: FixMsg) -> SessionOutcome:
    """Process an incoming FIX message according to session sequence rules.

    Rules R-S1 to R-S7:
    - R-S3: If msg.epoch != session.epoch: DISCARDED(EPOCH)
    - R-S4: If msg.seq < next_seq:
        - If poss_dup: DISCARDED(DUPLICATE)
        - Otherwise: DISCARDED(SEQ_TOO_LOW)
    - R-S5, R-S7: If msg.seq == next_seq:
        - add msg to to_process
        - next_seq += 1
        - drain consecutive messages from buffer
    - R-S6: If msg.seq > next_seq:
        - if msg.seq in buffer: DISCARDED(DUPLICATE_BUFFERED)
        - else: buffer[msg.seq] = msg, report BUFFERED
    """
    to_process: list[FixMsg] = []
    reports: list[Report] = []

    # Rule R-S3: epoch check
    if msg.epoch != session.epoch:
        reports.append(Report.discarded("EPOCH"))
        return SessionOutcome(to_process=to_process, reports=reports)

    # Rule R-S4: sequence too low
    if msg.seq < session.next_seq:
        if msg.poss_dup:
            reports.append(Report.discarded("DUPLICATE"))
        else:
            reports.append(Report.discarded("SEQ_TOO_LOW"))
        return SessionOutcome(to_process=to_process, reports=reports)

    # Rule R-S5, R-S7: expected sequence arrived
    if msg.seq == session.next_seq:
        to_process.append(msg)
        session.next_seq += 1

        # Drain consecutive messages from buffer
        while session.next_seq in session.buffer:
            buffered_msg = session.buffer.pop(session.next_seq)
            to_process.append(buffered_msg)
            session.next_seq += 1

        return SessionOutcome(to_process=to_process, reports=reports)

    # Rule R-S6: gap ahead
    if msg.seq in session.buffer:
        reports.append(Report.discarded("DUPLICATE_BUFFERED"))
    else:
        session.buffer[msg.seq] = msg
        reports.append(Report.buffered())

    return SessionOutcome(to_process=to_process, reports=reports)

from exchange_core.state import SessionState
from exchange_core.types import Event, Report


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
