"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from typing import Any
from exchange_core.types import Event, Report, BasketLeg
from exchange_core.state import EngineState
from exchange_core.handlers.new_limit import handle_new_limit

def handle_basket(engine: Any, event: Event) -> list[Report]:
    """Process a BASKET event with all-or-nothing rollback semantics."""
    snapshot = engine.state.snapshot()
    all_reports: list[Report] = []

    for i, leg in enumerate(event.legs):
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag
        )
        
        # Execute the leg
        leg_reports = handle_new_limit(engine, leg_event)
        
        # Determine failure according to Rule R-A3
        failed = False
        
        # Check if the leg was rejected
        if any(r.kind == "REJECTED" for r in leg_reports):
            failed = True
        else:
            # Locate the relevant order (the one just created by this leg)
            # The order_id is in the ACCEPTED report
            acc_report = next((r for r in leg_reports if r.kind == "ACCEPTED"), None)
            
            if leg.flag == "IOC":
                # IOC succeeds if leaves == 0
                if acc_report:
                    order = engine.state.orders.get(acc_report.order_id)
                    if order and order.leaves > 0:
                        failed = True
                else:
                    # If not accepted, it must have been fully filled immediately
                    if not any(r.kind == "FILL" for r in leg_reports):
                        failed = True
            
            elif leg.flag == "POST_ONLY":
                # POST_ONLY must be accepted and not cross (already handled by handle_new_limit)
                if not acc_report:
                    failed = True
        
        if failed:
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index=i)]
        
        all_reports.extend(leg_reports)

    all_reports.append(Report.basket_committed())
    return all_reports
