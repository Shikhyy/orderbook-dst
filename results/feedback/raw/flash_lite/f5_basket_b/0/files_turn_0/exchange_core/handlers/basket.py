"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report, Order
from exchange_core.handlers.new_limit import handle_new_limit


def handle_basket(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a BASKET event with all-or-nothing rollback semantics."""
    snapshot = engine.state.snapshot()
    all_reports = []

    for i, leg in enumerate(event.legs):
        # Create a NEW_LIMIT event for each leg
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag
        )

        reports = handle_new_limit(engine, leg_event)
        
        # Check success conditions (R-A3)
        failed = False
        
        # A rejected leg fails
        if any(r.kind == "REJECTED" for r in reports):
            failed = True
        
        # Check IOC condition
        if leg.flag == "IOC":
            # Must be accepted and have 0 leaves (fully matched)
            # Find the accepted order ID if any
            accepted_id = None
            for r in reports:
                if r.kind == "ACCEPTED":
                    accepted_id = r.order_id
            
            if accepted_id is None:
                failed = True
            else:
                order = engine.state.orders.get(accepted_id)
                # If order exists and has remaining volume, it means IOC_REMAINDER occurred
                if order and order.leaves > 0:
                    failed = True
                    
        # Check POST_ONLY condition
        if leg.flag == "POST_ONLY":
            # Must be accepted, but if it would cross it is rejected by new_limit
            # We already check for REJECTED, so if accepted, it succeeds.
            if accepted_id := next((r.order_id for r in reports if r.kind == "ACCEPTED"), None):
                # Ensure no fills occurred for a POST_ONLY order (would imply crossing)
                if any(r.kind == "FILL" for r in reports):
                    failed = True
            else:
                failed = True

        if failed:
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index=i)]
        
        all_reports.extend(reports)

    all_reports.append(Report.basket_committed())
    return all_reports
