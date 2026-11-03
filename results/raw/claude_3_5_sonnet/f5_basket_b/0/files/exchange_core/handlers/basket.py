"""exchange_core/handlers/basket.py
Handle atomic BASKET event execution with rollback.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process an atomic multi-leg basket order.

    Rules R-A1 to R-A5:
    - R-A2: Take snapshot before leg 1. Process each leg in order as NEW_LIMIT.
    - R-A3: An IOC leg succeeds if accepted and leaves is 0 after matching.
            A POST_ONLY leg succeeds if accepted. A rejected leg fails.
    - R-A4: If a leg fails, restore snapshot. Report BASKET_ROLLED_BACK(leg_index).
            Discard reports of earlier legs.
    - R-A5: If all legs succeed, report all leg reports in order + BASKET_COMMITTED.
    """
    # Rule R-A2: snapshot complete state before processing leg 1
    snap = engine.state.snapshot()

    all_leg_reports: list[Report] = []

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

        # Rule R-A3: leg success evaluation
        # 1. Any rejection fails the leg
        if any(r.kind == "REJECTED" for r in leg_reports):
            engine.state.restore(snap)
            return [Report.basket_rolled_back(leg_index)]

        # 2. IOC leg must have leaves == 0 after matching (cannot have IOC_REMAINDER)
        if leg.flag == "IOC":
            has_ioc_cancel = any(
                r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"
                for r in leg_reports
            )
            if has_ioc_cancel:
                engine.state.restore(snap)
                return [Report.basket_rolled_back(leg_index)]

        all_leg_reports.extend(leg_reports)

    # Rule R-A5: all legs succeeded
    all_leg_reports.append(Report.basket_committed())
    return all_leg_reports
