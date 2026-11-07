"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from typing import Any

from exchange_core.types import Event, Report


def handle_basket(engine: Any, event: Event) -> list[Report]:
    """Process a BASKET event with all-or-nothing rollback semantics."""
    snap = engine.state.snapshot()
    reports: list[Report] = []

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
        reports.extend(leg_reports)

        accepted_ids = [r.order_id for r in leg_reports if r.kind == "ACCEPTED"]
        has_rejection = any(r.kind == "REJECTED" for r in leg_reports)

        if has_rejection or not accepted_ids:
            engine.state.restore(snap)
            return [Report.basket_rolled_back(leg_index)]

        if leg.flag == "IOC":
            has_ioc_remainder = any(
                r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"
                for r in leg_reports
            )
            order = engine.state.orders.get(accepted_ids[0])
            leaves = order.leaves if order is not None else 0

            if has_ioc_remainder or leaves != 0:
                engine.state.restore(snap)
                return [Report.basket_rolled_back(leg_index)]

    reports.append(Report.basket_committed())
    return reports
