"""exchange_core/rules/session_rule.py
Pure function for FIX session sequence decisions.
Rules R-S1 to R-S5.
"""
from exchange_core.state import SessionState
from exchange_core.types import FixMsg, Report, SessionOutcome


def on_message(session: SessionState, msg: FixMsg) -> SessionOutcome:
    """Process an incoming FIX message according to session sequence rules."""
    # R-S2: reject messages from another epoch.
    if msg.epoch != session.epoch:
        return SessionOutcome(
            to_process=[],
            reports=[Report.discarded("EPOCH")],
        )

    # R-S3: sequence number already passed.
    if msg.seq < session.next_seq:
        if msg.poss_dup:
            reason = "DUPLICATE"
        else:
            reason = "SEQ_TOO_LOW"
        return SessionOutcome(
            to_process=[],
            reports=[Report.discarded(reason)],
        )

    # R-S4: expected sequence number; accept and drain the buffer.
    if msg.seq == session.next_seq:
        to_process = [msg]
        session.next_seq += 1

        while session.next_seq in session.buffer:
            buffered_msg = session.buffer.pop(session.next_seq)
            to_process.append(buffered_msg)
            session.next_seq += 1

        return SessionOutcome(to_process=to_process, reports=[])

    # R-S5: future sequence number; buffer it unless already buffered.
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
