"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from typing import Any

from exchange_core.types import Event, Report


def _leg_succeeded(flag: str, reports: list[Report]) -> bool:
    """Decide whether a leg succeeded according to Rule R-A3."""
    for r in reports:
        if r.kind == "REJECTED":
            return False
    if flag == "IOC":
        for r in reports:
            if r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER":
                return False
        return True
    if flag == "POST_ONLY":
        if any(r.kind == "FILL" for r in reports):
            return False
    return any(r.kind == "ACCEPTED" for r in reports)


def handle_basket(engine: Any, event: Event) -> list[Report]:
    """Process a BASKET event with all-or-nothing rollback semantics."""
    state = engine.state
    snap = state.snapshot()
    collected: list[Report] = []

    for index, leg in enumerate(event.legs):
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag,
        )
        reports = engine.dispatch(leg_event)
        if not _leg_succeeded(leg.flag, reports):
            state.restore(snap)
            return [Report.basket_rolled_back(index)]
        collected.extend(reports)

    collected.append(Report.basket_committed())
    return collected
