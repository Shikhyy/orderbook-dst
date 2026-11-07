"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report, Order
from exchange_core.book import get_order


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a BASKET event with all-or-nothing rollback semantics."""
    snapshot = engine.state.snapshot()
    reports = []
    
    for i, leg in enumerate(event.legs):
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag
        )
        
        leg_reports = engine.dispatch(leg_event)
        
        # Check for failure
        failed = False
        
        # Rule R-A3: Verify acceptance and success criteria
        accepted = any(r.kind == "ACCEPTED" for r in leg_reports)
        if not accepted:
            failed = True
        else:
            # Must not have specific failures
            # For POST_ONLY: must not cross (rejected)
            # For IOC: must not have REMAINDER (cancelled)
            for r in leg_reports:
                if r.kind == "REJECTED":
                    failed = True
                if r.kind == "CANCELLED" and leg.flag == "IOC":
                    failed = True
            
            # Additional check for IOC: must fill completely
            if not failed and leg.flag == "IOC":
                # Find the order ID from the accepted report
                order_id = next(r.order_id for r in leg_reports if r.kind == "ACCEPTED")
                order = get_order(engine.state, order_id)
                if order is not None and order.leaves > 0:
                    failed = True
                    
        if failed:
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index=i)]
        
        reports.extend(leg_reports)
        
    reports.append(Report.basket_committed())
    return reports
