"""exchange_core/handlers/basket.py"""
from exchange_core.types import Event, Report


def _rollback(engine, snap):
    engine.state.restore(snap)


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
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

        if any(r.kind == "REJECTED" for r in leg_reports):
            _rollback(engine, snap)
            return [Report.basket_rolled_back(leg_index)]

        if leg.flag == "IOC":
            has_ioc_cancel = any(
                r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"
                for r in leg_reports
            )
            if has_ioc_cancel:
                _rollback(engine, snap)
                return [Report.basket_rolled_back(leg_index)]
        
        # POST_ONLY leg must not cross (i.e., must not have resulted in a FILL)
        if leg.flag == "POST_ONLY":
            has_fill = any(r.kind == "FILL" for r in leg_reports)
            if has_fill:
                _rollback(engine, snap)
                return [Report.basket_rolled_back(leg_index)]

        all_leg_reports.extend(leg_reports)

    all_leg_reports.append(Report.basket_committed())
    return all_leg_reports
