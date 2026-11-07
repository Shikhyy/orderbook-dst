"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a BASKET event with all-or-nothing rollback semantics."""
    # Take snapshot before processing any legs (R-A2)
    snapshot = engine.state.snapshot()
    
    all_reports = []
    
    for leg_index, leg in enumerate(event.legs):
        # Create NEW_LIMIT event for this leg (R-A2)
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag,
        )
        
        # Dispatch the leg event
        leg_reports = engine.dispatch(leg_event)
        
        # Check if leg succeeded (R-A3)
        leg_succeeded = False
        
        if not leg_reports:
            # No reports means something went wrong, treat as failure
            leg_succeeded = False
        elif leg_reports[0].kind == "REJECTED":
            # Rejected leg fails (R-A3)
            leg_succeeded = False
        elif leg.flag == "IOC":
            # IOC leg succeeds if accepted and no IOC_REMAINDER cancellation (R-A3)
            has_ioc_remainder = any(
                r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"
                for r in leg_reports
            )
            leg_succeeded = not has_ioc_remainder
        elif leg.flag == "POST_ONLY":
            # POST_ONLY leg succeeds if accepted (R-A3)
            # If it crossed, it would be REJECTED (handled above)
            leg_succeeded = leg_reports[0].kind == "ACCEPTED"
        else:
            # NONE flag or other - treat as accepted if first report is ACCEPTED
            leg_succeeded = leg_reports[0].kind == "ACCEPTED"
        
        if not leg_succeeded:
            # Leg failed: restore snapshot and report rollback (R-A4)
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index=leg_index)]
        
        # Leg succeeded: collect reports
        all_reports.extend(leg_reports)
    
    # All legs succeeded: report all leg reports then BASKET_COMMITTED (R-A5)
    all_reports.append(Report.basket_committed())
    return all_reports
