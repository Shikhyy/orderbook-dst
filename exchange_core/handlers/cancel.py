"""exchange_core/handlers/cancel.py
Handle CANCEL event.
Rule R-C1.
"""
from exchange_core.book import get_order, remove_order
from exchange_core.types import Event, Report


def handle_cancel(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Cancel a resting order.

    Rule R-C1 [Common]:
    A CANCEL event for a resting order removes the order. It releases the full lock.
    It reports CANCELLED(order_id, USER).
    If the order is not resting, it reports REJECTED(UNKNOWN_ORDER).
    """
    state = engine.state
    order = get_order(state, event.order_id)
    if order is None or order.leaves <= 0:
        return [Report.rejected("UNKNOWN_ORDER")]

    # Remove order from book
    remove_order(state, order.order_id)

    # Release full lock to account free_cash
    state.accounts[order.account].locked_margin -= order.lock
    state.accounts[order.account].free_cash += order.lock
    order.lock = 0

    return [Report.cancelled(order.order_id, "USER")]
