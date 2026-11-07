"""exchange_core/rules/session_rule.py
Pure function for FIX session sequence decisions.
Rules R-S1 to R-S5. Target for task f3_fix_a.
"""
from exchange_core.state import SessionState
from exchange_core.types import Event, SessionOutcome, Report


def on_message(session: SessionState, msg: Event) -> SessionOutcome:
    """Process an incoming FIX message according to session sequence rules."""
    # R-S2: Check epoch
    if msg.epoch != session.epoch:
        return SessionOutcome(reports=[Report.discarded("EPOCH")])

    # R-S3: Sequence too low
    if msg.seq < session.next_seq:
        if msg.poss_dup:
            return SessionOutcome(reports=[Report.discarded("DUPLICATE")])
        else:
            return SessionOutcome(reports=[Report.discarded("SEQ_TOO_LOW")])

    # R-S5: Sequence higher than expected (Gap/Buffer)
    if msg.seq > session.next_seq:
        if msg.seq in session.buffer:
            return SessionOutcome(reports=[Report.discarded("DUPLICATE_BUFFERED")])
        else:
            session.buffer[msg.seq] = msg
            return SessionOutcome(reports=[Report.buffered()])

    # R-S4: Sequence matches (Process and drain buffer)
    to_process = [msg]
    session.next_seq += 1
    
    # Drain consecutive buffered messages
    while session.next_seq in session.buffer:
        buffered_msg = session.buffer.pop(session.next_seq)
        to_process.append(buffered_msg)
        session.next_seq += 1
        
    return SessionOutcome(to_process=to_process)
