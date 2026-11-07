"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from typing import Any
from exchange_core.types import Event, Report


def handle_basket(engine: Any, event: Event) -> list[Report]:
    """Process a BASKET event with all-or-nothing rollback semantics."""
    # R-A2: Take a snapshot of the complete state before processing any leg.
    snap = engine.state.snapshot()
    
    all_reports: list[Report] = []
    
    for i, leg in enumerate(event.legs):
        # R-A1/A2: Convert leg to NEW_LIMIT event.
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag
        )
        
        # Process the leg using engine.dispatch.
        leg_reports = engine.dispatch(leg_event)
        
        # R-A3: Check if the leg succeeded.
        # A leg is rejected if it returns a REJECTED report.
        # For IOC legs, they must not have an IOC_REMAINDER cancellation.
        failed = False
        for r in leg_reports:
            if r.kind == "REJECTED" or (r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER"):
                failed = True
                break
        
        if failed:
            # R-A4: If a leg fails, stop, restore, and report BASKET_ROLLED_BACK.
            engine.state.restore(snap)
            return [Report.basket_rolled_back(leg_index=i)]
        
        all_reports.extend(leg_reports)

    # R-A5: If all legs succeed, report all leg reports in order, then BASKET_COMMITTED.
    all_reports.append(Report.basket_committed())
    return all_reports
