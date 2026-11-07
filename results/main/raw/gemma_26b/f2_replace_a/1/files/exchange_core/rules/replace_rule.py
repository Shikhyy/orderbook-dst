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
    # R-P2 Step 2: Validate price
    if new_price <= 0 or new_price % cfg.TICK != 0:
        return ReplaceDecision(ok=False, reason="INVALID_ORDER", keep_priority=False, new_leaves=0)

    # R-P2 Step 3: Validate quantity
    # new_qty is the new total order quantity.
    # It must be greater than the already filled quantity.
    if new_qty <= order.cum_qty:
        return ReplaceDecision(ok=False, reason="INVALID_REPLACE", keep_priority=False, new_leaves=0)

    # Calculate new leaves
    new_leaves = new_qty - order.cum_qty

    # R-P3: Priority determination
    # - If new_price == old price and new_qty < old qty: keep priority.
    # - If new_price == old price and new_qty == old qty: keep priority (noop).
    # - Otherwise (price change or quantity increase): lose priority.
    keep_priority = False
    if new_price == order.price and new_qty <= order.qty:
        keep_priority = True

    return ReplaceDecision(
        ok=True,
        reason="",
        keep_priority=keep_priority,
        new_leaves=new_leaves
    )
