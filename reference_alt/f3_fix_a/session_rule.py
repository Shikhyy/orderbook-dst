"""exchange_core/rules/session_rule.py
Pure FIX session message handling rules R-S1 to R-S7.
"""
from exchange_core.state import SessionState
from exchange_core.types import FixMsg, Report, SessionOutcome


def on_message(session: SessionState, msg: FixMsg) -> SessionOutcome:
    """Handle incoming FIX message sequencing and buffering.

    Rules R-S1 to R-S7.
    """
    # Rule R-S3: epoch check
    if msg.epoch != session.epoch:
        return SessionOutcome(reports=[Report.discarded("EPOCH")])

    # Rule R-S4: seq too low / duplicate
    if msg.seq < session.next_seq:
        if msg.poss_dup:
            return SessionOutcome(reports=[Report.discarded("DUPLICATE")])
        return SessionOutcome(reports=[Report.discarded("SEQ_TOO_LOW")])

    # Rule R-S5 & R-S7: expected sequence
    if msg.seq == session.next_seq:
        to_process = [msg]
        session.next_seq += 1
        while session.next_seq in session.buffer:
            buffered_msg = session.buffer.pop(session.next_seq)
            to_process.append(buffered_msg)
            session.next_seq += 1
        return SessionOutcome(to_process=to_process, reports=[])

    # Rule R-S6: out-of-order sequence (msg.seq > session.next_seq)
    if msg.seq in session.buffer:
        return SessionOutcome(reports=[Report.discarded("DUPLICATE_BUFFERED")])

    session.buffer[msg.seq] = msg
    return SessionOutcome(reports=[Report.buffered()])
