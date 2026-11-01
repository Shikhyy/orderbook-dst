"""exchange_core/book.py
Book primitives. Derived views of resting orders in EngineState.
No rule logic belongs here (docs/03_ARCHITECTURE.md).
"""
from typing import Optional

from exchange_core.state import EngineState
from exchange_core.types import Order


def add_order(state: EngineState, order: Order) -> None:
    """Add a resting order to the state."""
    state.orders[order.order_id] = order


def remove_order(state: EngineState, order_id: int) -> Optional[Order]:
    """Remove and return a resting order by order_id."""
    return state.orders.pop(order_id, None)


def get_order(state: EngineState, order_id: int) -> Optional[Order]:
    """Retrieve a resting order by order_id."""
    return state.orders.get(order_id)


def get_bids(state: EngineState) -> list[Order]:
    """Return all resting BUY orders in priority order (Rule R-B2)."""
    bids = [o for o in state.orders.values() if o.side == "BUY" and o.leaves > 0]
    bids.sort(key=lambda o: (-o.price, o.prio_seq))
    return bids


def get_asks(state: EngineState) -> list[Order]:
    """Return all resting SELL orders in priority order (Rule R-B2)."""
    asks = [o for o in state.orders.values() if o.side == "SELL" and o.leaves > 0]
    asks.sort(key=lambda o: (o.price, o.prio_seq))
    return asks


def best_bid(state: EngineState) -> Optional[int]:
    """Return highest bid price, or None if no bids exist."""
    bids = get_bids(state)
    return bids[0].price if bids else None


def best_ask(state: EngineState) -> Optional[int]:
    """Return lowest ask price, or None if no asks exist."""
    asks = get_asks(state)
    return asks[0].price if asks else None


def get_account_orders(state: EngineState, account: str) -> list[Order]:
    """Return all resting orders for an account, sorted by prio_seq ascending (Rule R-W3)."""
    orders = [o for o in state.orders.values() if o.account == account and o.leaves > 0]
    orders.sort(key=lambda o: o.prio_seq)
    return orders
