"""exchange_core/handlers/basket.py
Handler for atomic multi-leg basket orders.
Rules R-A1 to R-A5. Target for task f5_basket_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import EngineState
from exchange_core.book import get_bids, get_asks

def handle_basket(engine: "Engine", event: Event) -> list[Report]:
    """Process a BASKET event with all-or-nothing rollback semantics."""
    snapshot = engine.state.snapshot()
    reports = []

    for leg_index, leg in enumerate(event.legs):
        # Create NEW_LIMIT event for the leg
        leg_event = Event(
            kind="NEW_LIMIT",
            account=event.account,
            side=leg.side,
            price=leg.price,
            qty=leg.qty,
            flag=leg.flag
        )

        # Process the leg
        leg_reports = engine.dispatch(leg_event)

        # Check if the leg was rejected
        if any(report.kind == "REJECTED" for report in leg_reports):
            engine.state.restore(snapshot)
            return [Report.basket_rolled_back(leg_index)]

        # Check IOC leg success condition (leaves == 0)
        if leg.flag == "IOC":
            # Get the order_id of the newly created order
            order_id = engine.state.next_order_id - 1
            order = engine.state.orders.get(order_id)
            if order and order.leaves != 0:
                engine.state.restore(snapshot)
                return [Report.basket_rolled_back(leg_index)]

        # Check POST_ONLY leg success condition (no crossing)
        if leg.flag == "POST_ONLY":
            if leg.side == "BUY":
                best_ask = get_asks(engine.state)
                if best_ask and leg.price > best_ask[0].price:
                    engine.state.restore(snapshot)
                    return [Report.basket_rolled_back(leg_index)]
            else:  # leg.side == "SELL"
                best_bid = get_bids(engine.state)
                if best_bid and leg.price < best_bid[0].price:
                    engine.state.restore(snapshot)
                    return [Report.basket_rolled_back(leg_index)]

        # Add the leg reports to the overall reports
        reports.extend(leg_reports)

    # If all legs succeeded, commit the basket
    reports.append(Report.basket_committed())
    return reports
