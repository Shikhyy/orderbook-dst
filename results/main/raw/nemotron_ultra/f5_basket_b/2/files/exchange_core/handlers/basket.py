"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a BASKET event with all-or-nothing rollback semantics."""
    # Take snapshot before processing any legs (R-A2)
    snapshot = engine.state.snapshot()
    
    all_reports: list[Report] = []
    
    # Process each leg in order (R-A2)
    for leg_index, leg in enumerate(event.legs):
        # Create NEW_LIMIT event for this leg (R-A1)
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag,
        )
        
        # Dispatch the leg through the engine
        leg_reports = engine.dispatch(leg_event)
        
        # Check if leg was rejected (R-A3)
        if not leg_reports or leg_reports[0].kind == "REJECTED":
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index)]
        
        # Leg must be accepted to proceed
        if leg_reports[0].kind != "ACCEPTED":
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index)]
        
        order_id = leg_reports[0].order_id
        
        # Flag-specific success criteria (R-A3)
        if leg.flag == "IOC":
            # IOC succeeds if accepted and leaves == 0 (no IOC_REMAINDER cancellation)
            has_ioc_remainder = any(
                r.kind == "CANCELLED" and r.reason == "IOC_REMAINDER" and r.order_id == order_id
                for r in leg_reports
            )
            if has_ioc_remainder:
                engine.state.restore(snapshot)
                return [Report.basket_rolled_back(leg_index)]
            
            # Also verify order has no leaves remaining (defensive)
            order = engine.state.orders.get(order_id)
            if order is not None and order.leaves > 0:
                engine.state.restore(snapshot)
                return [Report.basket_rolled_back(leg_index)]
                
        elif leg.flag == "POST_ONLY":
            # POST_ONLY succeeds if accepted (acceptance implies no cross)
            pass
        
        # Leg succeeded - collect its reports
        all_reports.extend(leg_reports)
    
    # All legs succeeded (R-A5)
    all_reports.append(Report.basket_committed())
    return all_reports
