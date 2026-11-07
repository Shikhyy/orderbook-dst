"""exchange_core/rules/session_rule.py
Pure function for FIX session sequence decisions.
Rules R-S1 to R-S7. Target for task f3_fix_a.
"""
from exchange_core.state import SessionState
from exchange_core.types import FixMsg, SessionOutcome, Report

def on_message(session: SessionState, msg: FixMsg) -> SessionOutcome:
    """Process an incoming FIX message according to session sequence rules."""
    outcome = SessionOutcome()

    # Rule R-S2: Check epoch mismatch
    if msg.epoch != session.epoch:
        outcome.reports.append(Report.discarded("EPOCH"))
        return outcome

    # Rule R-S3: Check seq < next_seq
    if msg.seq < session.next_seq:
        if msg.poss_dup:
            outcome.reports.append(Report.discarded("DUPLICATE"))
        else:
            outcome.reports.append(Report.discarded("SEQ_TOO_LOW"))
        return outcome

    # Rule R-S4: Check seq == next_seq
    if msg.seq == session.next_seq:
        outcome.to_process.append(msg)
        session.next_seq += 1

        # Drain buffered messages in order
        while session.buffer and session.next_seq in session.buffer:
            buffered_msg = session.buffer.pop(session.next_seq)
            outcome.to_process.append(buffered_msg)
            session.next_seq += 1

        return outcome

    # Rule R-S5: Check seq > next_seq
    if msg.seq in session.buffer:
        outcome.reports.append(Report.discarded("DUPLICATE_BUFFERED"))
    else:
        session.buffer[msg.seq] = msg
        outcome.reports.append(Report.buffered())

    return outcome
