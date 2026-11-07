"""exchange_core/rules/replace_rule.py
Pure function for replace decisions.
Rules R-P1, R-P2 (steps 2, 3), and R-P3. Target for task f2_replace_a.
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

    Rules R-P1, R-P2 (steps 2 and 3), R-P3.
    """
    # R-P2 step 2: Invalid price check
    if new_price <= 0 or new_price % cfg.tick != 0:
        return ReplaceDecision(ok=False, reason="INVALID_ORDER", keep_priority=False, new_leaves=0)

    # R-P2 step 3: Invalid quantity check (new_qty is total quantity, must be > cum_qty)
    if new_qty <= order.cum_qty:
        return ReplaceDecision(ok=False, reason="INVALID_REPLACE", keep_priority=False, new_leaves=0)

    # Valid replace - compute new leaves
    new_leaves = new_qty - order.cum_qty

    # R-P3: Priority rules
    # Keep priority if price unchanged AND new_qty <= old qty
    keep_priority = (new_price == order.price and new_qty <= order.qty)

    return ReplaceDecision(ok=True, reason="", keep_priority=keep_priority, new_leaves=new_leaves)
