"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report, Order
from exchange_core.handlers.new_limit import handle_new_limit
from typing import Any


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
        
        reports = handle_new_limit(engine, leg_event)
        
        # Check for failure
        failed = False
        if not reports:
            failed = True
        else:
            last_rep = reports[-1]
            if last_rep.kind == "REJECTED":
                failed = True
            elif leg.flag == "IOC":
                # Check for remainder/cancellation (IOC_REMAINDER)
                # handle_new_limit for IOC typically results in ACCEPTED + FILLs
                # and if not fully filled, CANCELLED(IOC_REMAINDER)
                for r in reports:
                    if r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER":
                        failed = True
            elif leg.flag == "POST_ONLY":
                # Must not cross, must be accepted
                # If it crossed, it would have been rejected or filled against
                # check if accepted (only 1 report if accepted, or if it matched but failed?)
                # Rule R-A3: POST_ONLY succeeds if accepted (must not cross)
                # If engine returns REJECTED, handled above.
                if last_rep.kind != "ACCEPTED":
                    failed = True
        
        if failed:
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index=i)]
        
        all_reports.extend(reports)
        
    all_reports.append(Report.basket_committed())
    return all_reports
