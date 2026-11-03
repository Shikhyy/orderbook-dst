"""Cancel order handler.

Rule R-C1:
- A CANCEL event for a resting order removes the order.
- It releases the full lock.
- It reports CANCELLED(order_id, USER).
- If the order is not resting, it reports REJECTED(UNKNOWN_ORDER).
"""
from typing import Any

from exchange_core.book import get_order, remove_order
from exchange_core.ledger import release_lock
from exchange_core.types import Event, Report


def handle_cancel(engine: Any, event: Event) -> list[Report]:
    """Handle a CANCEL event.

    Rule R-C1:
    - If the order is not resting: REJECTED(UNKNOWN_ORDER).
    - If resting: remove order, release full lock to free_cash, report CANCELLED(order_id, USER).
    """
    order = get_order(engine.state, event.order_id)
    if order is None:
        return [Report.rejected("UNKNOWN_ORDER")]

    remove_order(engine.state, event.order_id)
    release_lock(engine.state, order.account, order.lock)
    order.lock = 0
    return [Report.cancelled(event.order_id, "USER")]
