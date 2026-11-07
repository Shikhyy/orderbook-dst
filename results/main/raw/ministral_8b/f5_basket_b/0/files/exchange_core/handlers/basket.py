"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import EngineState

def handle_basket(engine: "Engine", event: Event) -> list[Report]:
    """Process a BASKET event with all-or-nothing rollback semantics."""
    # Take a snapshot of the current state
    snapshot = engine.state.snapshot()

    reports = []
    leg_index = 0

    for leg in event.legs:
        # Create a NEW_LIMIT event for the current leg
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag
        )

        # Process the leg event
        leg_reports = engine.dispatch(leg_event)

        # Check if the leg succeeded based on its flag and reports
        leg_success = False
        for report in leg_reports:
            if report.kind == "REJECTED":
                # Rollback to snapshot and return failure
                engine.state.restore(snapshot)
                return [Report.basket_rolled_back(leg_index)]

            if report.kind == "ACCEPTED":
                leg_success = True

            if leg.flag == "IOC" and report.kind == "FILL":
                # Check if IOC leg was fully matched (leaves == 0)
                # We need to check if the order was cancelled due to IOC_REMAINDER
                # by looking for a CANCELLED report with reason "IOC_REMAINDER"
                ioc_remainder = any(
                    r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"
                    for r in leg_reports
                )
                if ioc_remainder:
                    # Rollback to snapshot and return failure
                    engine.state.restore(snapshot)
                    return [Report.basket_rolled_back(leg_index)]

            if leg.flag == "POST_ONLY":
                # Check if POST_ONLY leg crossed the market
                # If there's a FILL report, it means it crossed
                if report.kind == "FILL":
                    # Rollback to snapshot and return failure
                    engine.state.restore(snapshot)
                    return [Report.basket_rolled_back(leg_index)]

        if not leg_success:
            # Rollback to snapshot and return failure
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index)]

        # Add reports for this leg
        reports.extend(leg_reports)
        leg_index += 1

    # If all legs succeeded, commit the basket
    reports.append(Report.basket_committed())
    return reports
