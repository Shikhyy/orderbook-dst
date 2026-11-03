"""FIX session sequencing rules.

Rules:
- R-S2: Session state (epoch, next_seq, buffer).
- R-S3: Epoch mismatch -> DISCARDED(EPOCH).
- R-S4: seq < next_seq -> DISCARDED(DUPLICATE) if poss_dup else DISCARDED(SEQ_TOO_LOW).
- R-S5: seq == next_seq -> process body, increment next_seq, drain contiguous buffer.
- R-S6: seq > next_seq -> if in buffer DISCARDED(DUPLICATE_BUFFERED) else buffer and BUFFERED.
- R-S7: poss_dup flag does not prevent processing if seq == next_seq.
"""
from exchange_core.state import SessionState
from exchange_core.types import FixMsg, Report, SessionOutcome


def on_message(session: SessionState, msg: FixMsg) -> SessionOutcome:
    """Handle an incoming FIX message for a session.

    Returns a SessionOutcome containing admitted messages (in order)
    and any reports generated directly by sequence handling (discarded/buffered).
    """
    # R-S3: Epoch check
    if msg.epoch != session.epoch:
        return SessionOutcome(
            to_process=[],
            reports=[Report.discarded("EPOCH")],
        )

    # R-S4: Seq too low
    if msg.seq < session.next_seq:
        reason = "DUPLICATE" if msg.poss_dup else "SEQ_TOO_LOW"
        return SessionOutcome(
            to_process=[],
            reports=[Report.discarded(reason)],
        )

    # R-S6: Gap (seq > next_seq)
    if msg.seq > session.next_seq:
        if msg.seq in session.buffer:
            return SessionOutcome(
                to_process=[],
                reports=[Report.discarded("DUPLICATE_BUFFERED")],
            )
        session.buffer[msg.seq] = msg
        return SessionOutcome(
            to_process=[],
            reports=[Report.buffered()],
        )

    # R-S5 & R-S7: In-order arrival (msg.seq == session.next_seq)
    to_process = [msg]
    session.next_seq += 1

    # Drain contiguous buffered messages in ascending seq order
    while session.next_seq in session.buffer:
        buffered_msg = session.buffer.pop(session.next_seq)
        to_process.append(buffered_msg)
        session.next_seq += 1

    return SessionOutcome(to_process=to_process, reports=[])
