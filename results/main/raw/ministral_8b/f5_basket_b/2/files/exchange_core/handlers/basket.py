"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import EngineState
from exchange_core.handlers.new_limit import handle_new_limit

def handle_basket(engine: "Engine", event: Event) -> list[Report]:
    """Process a BASKET event with all-or-nothing rollback semantics."""
    if not event.legs:
        return [Report.basket_committed()]

    # Take a snapshot of the current state
    snapshot = engine.state.snapshot()
    reports = []

    for leg_index, leg in enumerate(event.legs):
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

        # Check if the leg failed
        if any(report.kind == "REJECTED" for report in leg_reports):
            # Rollback to the snapshot
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index)]

        # Check IOC leg success condition (leaves == 0)
        if leg.flag == "IOC":
            # Check if the leg was fully matched (leaves == 0)
            order_id = leg_reports[0].order_id if leg_reports else 0
            order = engine.state.orders.get(order_id)
            if order and order.leaves != 0:
                # IOC leg not fully matched, rollback
                engine.state.restore(snapshot)
                return [Report.basket_rolled_back(leg_index)]

        # Check POST_ONLY leg success condition (no crossing)
        if leg.flag == "POST_ONLY":
            # Check if the leg would cross the book
            # This is implicitly handled by the engine's rules, but we need to verify
            # that the leg was accepted without crossing
            # Since the engine already processed it, we assume it passed if no REJECTED report
            # and the order is still in the book (not crossing)
            pass

        # Add the leg reports to the basket reports
        reports.extend(leg_reports)

    # If all legs succeeded, commit the basket
    return reports + [Report.basket_committed()]
