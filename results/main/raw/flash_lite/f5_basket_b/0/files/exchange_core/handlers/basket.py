"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from typing import Any
from exchange_core.types import Event, Report, Order
from exchange_core.book import get_order


def handle_basket(engine: Any, event: Event) -> list[Report]:
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
        
        # Check if leg failed
        failed = False
        
        # Rule R-A3: Verify Acceptance and success condition
        # A leg fails if not accepted or violates specific logic (IOC/POST_ONLY)
        accepted = False
        for r in leg_reports:
            if r.kind == "ACCEPTED":
                accepted = True
                order_id = r.order_id
                break
        
        if not accepted:
            failed = True
        else:
            # Check for specific failure based on flag
            if leg.flag == "IOC":
                # IOC succeeds if leaves is 0 (fully filled)
                order = get_order(engine.state, order_id)
                if order is not None and order.leaves > 0:
                    failed = True
            elif leg.flag == "POST_ONLY":
                # POST_ONLY fails if it crossed (must be resting)
                order = get_order(engine.state, order_id)
                # If it didn't stay as an order, it crossed and was filled/cancelled
                if order is None:
                    failed = True
                    
        if failed:
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index=i)]
        
        reports.extend(leg_reports)
    
    reports.append(Report.basket_committed())
    return reports
