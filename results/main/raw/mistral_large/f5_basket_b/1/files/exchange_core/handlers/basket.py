"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from typing import Any

from exchange_core.types import Event, Report


def _leg_succeeded(engine: Any, reports: list[Report], flag: str) -> bool:
    """Return True if a processed basket leg satisfies Rule R-A3."""
    if any(r.kind == "REJECTED" for r in reports):
        return False

    accepted = [r for r in reports if r.kind == "ACCEPTED"]
    if not accepted:
        return False

    if flag == "IOC":
        # An IOC leg must be fully filled: no IOC remainder may remain.
        if any(r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER" for r in reports):
            return False
        order = engine.state.orders.get(accepted[-1].order_id)
        if order is not None and order.leaves != 0:
            return False

    # A POST_ONLY leg succeeds whenever it is accepted; a crossing POST_ONLY
    # order is rejected by the NEW_LIMIT handler before acceptance.
    return True


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
        reports = engine.dispatch(leg_event)

        if not _leg_succeeded(engine, reports, leg.flag):
            engine.state.restore(snap)
            return [Report.basket_rolled_back(leg_index)]

        all_reports.extend(reports)

    all_reports.append(Report.basket_committed())
    return all_reports
