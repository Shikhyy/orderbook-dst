"""exchange_core/rules/session_rule.py
Pure function for FIX session sequence decisions.
Rules R-S1 to R-S7. Target for task f3_fix_a.
"""
from exchange_core.state import SessionState
from exchange_core.types import FixMsg, Report, SessionOutcome


def on_message(session: SessionState, msg: FixMsg) -> SessionOutcome:
    """Process an incoming FIX message according to session sequence rules."""
    if msg.epoch != session.epoch:
        return SessionOutcome(to_process=[], reports=[Report.discarded("EPOCH")])

    if msg.seq < session.next_seq:
        reason = "DUPLICATE" if msg.poss_dup else "SEQ_TOO_LOW"
        return SessionOutcome(to_process=[], reports=[Report.discarded(reason)])

    if msg.seq > session.next_seq:
        if msg.seq in session.buffer:
            return SessionOutcome(
                to_process=[], reports=[Report.discarded("DUPLICATE_BUFFERED")]
            )
        session.buffer[msg.seq] = msg
        return SessionOutcome(to_process=[], reports=[Report.buffered()])

    to_process = [msg]
    session.next_seq += 1

    while session.next_seq in session.buffer:
        to_process.append(session.buffer.pop(session.next_seq))
        session.next_seq += 1

    return SessionOutcome(to_process=to_process, reports=[])
