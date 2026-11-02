"""exchange_core/rules/replace_rule.py
Pure replace decision rule R-P1, R-P2, R-P3.
"""
from exchange_core.config import EngineConfig
from exchange_core.types import Order, ReplaceDecision


def decide_replace(
    order: Order,
    new_price: int,
    new_qty: int,
    cfg: EngineConfig,
) -> ReplaceDecision:
    """Validate a replace request and determine queue priority.

    Rules R-P1, R-P2, R-P3.
    """
    if new_price <= 0 or new_price % cfg.tick != 0:
        return ReplaceDecision(ok=False, reason="INVALID_ORDER")
    if new_qty <= order.cum_qty:
        return ReplaceDecision(ok=False, reason="INVALID_REPLACE")

    new_leaves = new_qty - order.cum_qty
    keep_priority = (new_price == order.price and new_qty <= order.qty)
    return ReplaceDecision(
        ok=True,
        keep_priority=keep_priority,
        new_leaves=new_leaves,
    )
