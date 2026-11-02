"""exchange_core/handlers/basket.py
Handle BASKET event.
Rules R-A1 to R-A5.
"""
from typing import Any

from exchange_core.handlers.new_limit import handle_new_limit
from exchange_core.types import Event, Report


def handle_basket(engine: Any, event: Event) -> list[Report]:
    """Handle atomic basket of orders.

    Rules R-A1 to R-A5.
    """
    snapshot = engine.state.snapshot()
    basket_reports: list[Report] = []

    for idx, leg in enumerate(event.legs):
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag,
        )
        leg_reports = handle_new_limit(engine, leg_event)

        # Check leg success (Rule R-A3)
        # IOC leg succeeds if accepted and leaves == 0 (no IOC_REMAINDER cancellation)
        # POST_ONLY leg succeeds if accepted
        # Any rejected leg fails
        if not leg_reports or leg_reports[0].kind != "ACCEPTED":
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(idx)]

        if leg.flag == "IOC":
            if any(r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER" for r in leg_reports):
                engine.state.restore(snapshot)
                return [Report.basket_rolled_back(idx)]

        basket_reports.extend(leg_reports)

    return basket_reports + [Report.basket_committed()]
