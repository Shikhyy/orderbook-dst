"""Atomic basket execution handler.

Rules:
- R-A1 to R-A7: All-or-none atomic multi-leg execution with snapshot and rollback.
"""
from typing import Any

from exchange_core.types import Event, Report


def handle_basket(engine: Any, event: Event) -> list[Report]:
    """Handle a BASKET event atomically.

    Rules R-A1 to R-A7:
    - Takes snapshot of complete engine state before leg 1.
    - Processes each leg in order as a NEW_LIMIT event for the account.
    - Success conditions:
        - POST_ONLY: succeeds if accepted.
        - IOC: succeeds if accepted and leaves == 0 after matching (before remainder cancel).
    - If a leg fails: stops immediately, restores snapshot, reports BASKET_ROLLED_BACK(leg_index).
    - If all legs succeed: reports reports of all legs, then BASKET_COMMITTED.
    """
    snapshot = engine.state.snapshot()
    accumulated_reports: list[Report] = []

    for leg_index, leg in enumerate(event.legs):
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag,
        )
        leg_reports = engine.process(leg_event)

        # R-A3: A rejected leg fails.
        is_accepted = any(r.kind == "ACCEPTED" for r in leg_reports)
        if not is_accepted:
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index)]

        # R-A3, R-A7: IOC leg succeeds only if leaves == 0 after matching.
        # If leaves > 0, an IOC_REMAINDER cancellation report is emitted.
        if leg.flag == "IOC":
            had_remainder = any(
                r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"
                for r in leg_reports
            )
            if had_remainder:
                engine.state.restore(snapshot)
                return [Report.basket_rolled_back(leg_index)]

        accumulated_reports.extend(leg_reports)

    accumulated_reports.append(Report.basket_committed())
    return accumulated_reports
