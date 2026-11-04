"""mutants/f3_fix_b/m_skip_possdup/fix.py
Mutant that discards all poss_dup messages.
"""
from exchange_core.state import SessionState
from exchange_core.types import Event, FixMsg, Report, SessionOutcome

# --- Rule logic (session_rule), written out here because Variant B code may not
# import exchange_core.rules.* (see the task's 'Allowed imports'). ---

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
