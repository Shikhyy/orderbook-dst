"""exchange_core/invariants.py
Invariant checks I1, I2, and I3.
See docs/05_INVARIANTS_AND_DATA.md sections 2 and 3.
"""
from dataclasses import dataclass, field

from exchange_core.config import EngineConfig
from exchange_core.intmath import ceil_div
from exchange_core.state import EngineState


@dataclass
class Violation:
    """An invariant violation record.
    Rule INV-03, INV-04.
    """
    invariant: str  # "I1" ... "I4"
    plain_name: str
    event_index: int
    message: str
    diff: dict = field(default_factory=dict)


def _viol(inv: str, name: str, idx: int, msg: str, diff: dict) -> Violation:
    return Violation(invariant=inv, plain_name=name, event_index=idx, message=msg, diff=diff)


def check_i1(state: EngineState, event_index: int) -> list[Violation]:
    """I1: No money created or destroyed."""
    total_cash = sum(a.free_cash + a.locked_margin for a in state.accounts.values())
    current_total = total_cash + state.fee_vault
    if current_total != state.initial_total:
        return [_viol("I1", "No money created or destroyed", event_index,
                      f"total money {current_total} != initial {state.initial_total}",
                      {"expected": state.initial_total, "actual": current_total})]
    return []


def check_i2(state: EngineState, event_index: int) -> list[Violation]:
    """I2: Margin matches resting orders."""
    violations: list[Violation] = []
    for oid, o in state.orders.items():
        expected_lock = ceil_div(o.leaves * o.price * o.margin_bps, 10_000)
        if o.lock != expected_lock:
            violations.append(
                _viol(
                    "I2", "Margin matches resting orders", event_index,
                    f"order {oid} lock {o.lock} != expected {expected_lock}",
                    {"order_id": oid, "actual_lock": o.lock, "expected_lock": expected_lock},
                )
            )

    account_order_locks: dict[str, int] = {acc_id: 0 for acc_id in state.accounts}
    for o in state.orders.values():
        if o.account in account_order_locks:
            account_order_locks[o.account] += o.lock

    for acc_id, acc in state.accounts.items():
        expected_account_locked = account_order_locks[acc_id]
        if acc.locked_margin != expected_account_locked:
            violations.append(
                _viol(
                    "I2", "Margin matches resting orders", event_index,
                    f"account {acc_id} locked={acc.locked_margin}, "
                    f"resting obligation={expected_account_locked}",
                    {
                        "account": acc_id,
                        "locked": acc.locked_margin,
                        "expected": expected_account_locked,
                    },
                )
            )
    return violations


def check_i3(state: EngineState, event_index: int, tick: int = 10_000) -> list[Violation]:
    """I3: Book is sound."""
    violations: list[Violation] = []
    bids = [o for o in state.orders.values() if o.side == "BUY" and o.leaves > 0]
    asks = [o for o in state.orders.values() if o.side == "SELL" and o.leaves > 0]

    # 1. best_bid < best_ask
    if bids and asks:
        max_bid = max(o.price for o in bids)
        min_ask = min(o.price for o in asks)
        if max_bid >= min_ask:
            violations.append(_viol("I3", "Book is sound", event_index,
                                    f"crossed book: best_bid {max_bid} >= best_ask {min_ask}",
                                    {"best_bid": max_bid, "best_ask": min_ask}))

    # 2. Each resting order has leaves > 0
    for oid, o in state.orders.items():
        if o.leaves <= 0:
            violations.append(_viol("I3", "Book is sound", event_index,
                                    f"order {oid} has leaves {o.leaves} <= 0",
                                    {"order_id": oid, "leaves": o.leaves}))

    # 3. In each price level, strictly rising prio_seq
    from collections import defaultdict
    bids_by_price: dict[int, list] = defaultdict(list)
    asks_by_price: dict[int, list] = defaultdict(list)
    for o in bids:
        bids_by_price[o.price].append(o)
    for o in asks:
        asks_by_price[o.price].append(o)

    for price, orders in {**bids_by_price, **asks_by_price}.items():
        orders.sort(key=lambda o: o.prio_seq)
        for i in range(len(orders) - 1):
            if orders[i].prio_seq >= orders[i + 1].prio_seq:
                violations.append(_viol("I3", "Book is sound", event_index,
                                        f"price level {price} queue prio_seq not strictly rising",
                                        {"price": price}))

    # 4. No two orders have same prio_seq
    prio_seqs = [o.prio_seq for o in state.orders.values()]
    if len(prio_seqs) != len(set(prio_seqs)):
        violations.append(_viol("I3", "Book is sound", event_index,
                                "duplicate prio_seq found among resting orders",
                                {"count": len(prio_seqs), "unique": len(set(prio_seqs))}))

    # 5. Each resting order has valid price
    for oid, o in state.orders.items():
        if o.price <= 0 or o.price % tick != 0:
            violations.append(_viol("I3", "Book is sound", event_index,
                                    f"order {oid} has invalid price {o.price}",
                                    {"order_id": oid, "price": o.price}))

    return violations


def check_invariants(
    state: EngineState,
    event_index: int,
    cfg: EngineConfig = EngineConfig(),
) -> list[Violation]:
    """Check I1, I2, and I3 after an event. Returns list of violations found."""
    violations: list[Violation] = []
    violations.extend(check_i1(state, event_index))
    violations.extend(check_i2(state, event_index))
    violations.extend(check_i3(state, event_index, cfg.tick))
    return violations
