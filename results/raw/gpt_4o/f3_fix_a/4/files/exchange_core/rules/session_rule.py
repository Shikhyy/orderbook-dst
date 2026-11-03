"""mutants/f3_fix_a/m_process_out_of_order/session_rule.py
Mutant that processes gap messages immediately instead of buffering.
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

    # Mutant bug: processes out-of-order immediately without buffering
    to_process.append(msg)
    if msg.seq >= session.next_seq:
        session.next_seq = msg.seq + 1

    return SessionOutcome(to_process=to_process, reports=reports)
