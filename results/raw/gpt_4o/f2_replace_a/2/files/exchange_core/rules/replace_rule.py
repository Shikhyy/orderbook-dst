"""reference/f2_replace_a/replace_rule.py
Reference solution for task f2_replace_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.types import Order, ReplaceDecision


def decide_replace(
    order: Order,
    new_price: int,
    new_qty: int,
    cfg: EngineConfig,
) -> ReplaceDecision:
    """Decide whether a replace request is valid and whether it keeps priority.

    Rules R-P1, R-P2 (steps 2 and 3), R-P3:
    - Step 2: If new_price <= 0 or new_price % TICK != 0: REJECTED(INVALID_ORDER)
    - Step 3: If new_qty <= cum_qty: REJECTED(INVALID_REPLACE)
    - Priority:
      - If new_price == old_price and new_qty < old_qty: keeps prio_seq
      - If new_price == old_price and new_qty == old_qty: nothing changes (keeps prio_seq)
      - In all other cases (price change or qty increase): gets new prio_seq
    """
    # Rule R-P2 step 2: price validation
    if new_price <= 0 or new_price % cfg.tick != 0:
        return ReplaceDecision(ok=False, reason="INVALID_ORDER", keep_priority=False, new_leaves=0)

    # Rule R-P2 step 3: quantity vs cum_qty
    if new_qty <= order.cum_qty:
        return ReplaceDecision(
            ok=False, reason="INVALID_REPLACE", keep_priority=False, new_leaves=0
        )

    new_leaves = new_qty - order.cum_qty

    # Rule R-P3: priority determination
    if new_price == order.price and new_qty <= order.qty:
        keep_priority = True
    else:
        keep_priority = False

    return ReplaceDecision(
        ok=True,
        reason="",
        keep_priority=keep_priority,
        new_leaves=new_leaves,
    )
