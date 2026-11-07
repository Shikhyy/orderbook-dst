"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from typing import Any

from exchange_core.types import Event, Report


def handle_basket(engine: Any, event: Event) -> list[Report]:
    """Process a BASKET event with all-or-nothing rollback semantics."""
    snap = engine.state.snapshot()
    all_reports: list[Report] = []

    for leg_index, leg in enumerate(event.legs):
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag,
        )
        leg_reports = engine.dispatch(leg_event)

        has_accepted = any(r.kind == "ACCEPTED" for r in leg_reports)
        has_rejected = any(r.kind == "REJECTED" for r in leg_reports)
        has_cancelled = any(r.kind == "CANCELLED" for r in leg_reports)

        if not has_accepted or has_rejected or has_cancelled:
            engine.state.restore(snap)
            return [Report.basket_rolled_back(leg_index)]

        all_reports.extend(leg_reports)

    all_reports.append(Report.basket_committed())
    return all_reports
