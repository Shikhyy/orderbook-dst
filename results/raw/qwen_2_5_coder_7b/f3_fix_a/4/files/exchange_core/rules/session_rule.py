"""mutants/f3_fix_a/m_no_drain/session_rule.py
Mutant that fails to drain buffered messages when the gap is filled.
"""
from exchange_core.state import SessionState
from exchange_core.types import FixMsg, Report, SessionOutcome


def on_message(session: SessionState, msg: FixMsg) -> SessionOutcome:
    to_process: list[FixMsg] = []
    reports: list[Report] = []

    if msg.epoch != session.epoch:
        reports.append(Report.discarded("EPOCH"))
        return SessionOutcome(to_process=to_process, reports=reports)

    if msg.seq < session.next_seq:
        if msg.poss_dup:
            reports.append(Report.discarded("DUPLICATE"))
        else:
            reports.append(Report.discarded("SEQ_TOO_LOW"))
        return SessionOutcome(to_process=to_process, reports=reports)

    if msg.seq == session.next_seq:
        to_process.append(msg)
        session.next_seq += 1
        # Mutant bug: does NOT drain buffered messages
        return SessionOutcome(to_process=to_process, reports=reports)

    if msg.seq in session.buffer:
        reports.append(Report.discarded("DUPLICATE_BUFFERED"))
    else:
        session.buffer[msg.seq] = msg
        reports.append(Report.buffered())

    return SessionOutcome(to_process=to_process, reports=reports)
