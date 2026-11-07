"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report


def _leg_ok(flag: str, reports: list[Report]) -> bool:
    """Decide whether a leg succeeded (Rule R-A3)."""
    accepted = False
    for r in reports:
        if r.kind == "REJECTED":
            return False
        if r.kind == "ACCEPTED":
            accepted = True
    if not accepted:
        return False
    for r in reports:
        if r.kind == "CANCELLED":
            if flag == "IOC" and "IOC_REMAINDER" in r.reason:
                return False
            if flag == "POST_ONLY":
                return False
    return True


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a BASKET event with all-or-nothing rollback semantics."""
    state = engine.state
    snap = state.snapshot()
    all_reports: list[Report] = []

    for idx, leg in enumerate(event.legs):
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag,
        )
        reports = engine.dispatch(leg_event)
        if not _leg_ok(leg.flag, reports):
            state.restore(snap)
            return [Report.basket_rolled_back(idx)]
        all_reports.extend(reports)

    all_reports.append(Report.basket_committed())
    return all_reports
