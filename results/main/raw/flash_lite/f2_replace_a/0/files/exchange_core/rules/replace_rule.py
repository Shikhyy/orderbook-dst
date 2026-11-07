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
    # R-P2 Step 2: Price must be positive and divisible by TICK
    if new_price <= 0 or (new_price % cfg.TICK != 0):
        return ReplaceDecision(ok=False, reason="INVALID_ORDER", keep_priority=False, new_leaves=0)

    # R-P2 Step 3: new_qty must be greater than current cum_qty
    if new_qty <= order.cum_qty:
        return ReplaceDecision(ok=False, reason="INVALID_REPLACE", keep_priority=False, new_leaves=0)

    # R-P3: Determine priority
    # Keeps priority if price is unchanged and new_qty <= original qty
    # NOTE: Rule says "if new_qty is less than the old qty, the order keeps... its place"
    # Rule also says "If new_price equals the old price and new_qty equals the old qty, nothing changes."
    # R-P3: In all other cases (price change, or quantity increase), it loses priority.
    is_price_unchanged = (new_price == order.price)
    is_qty_not_increased = (new_qty <= order.qty)
    
    keep_priority = is_price_unchanged and is_qty_not_increased
    
    return ReplaceDecision(
        ok=True,
        reason="",
        keep_priority=keep_priority,
        new_leaves=new_qty - order.cum_qty
    )
