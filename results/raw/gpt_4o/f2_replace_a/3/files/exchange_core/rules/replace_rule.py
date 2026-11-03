"""Mutant m_allow_equal_cum: Uses < instead of <=, allowing new_qty == cum_qty."""
from exchange_core.config import EngineConfig
from exchange_core.types import Order, ReplaceDecision


def decide_replace(
    order: Order,
    new_price: int,
    new_qty: int,
    cfg: EngineConfig,
) -> ReplaceDecision:
    if new_price <= 0 or new_price % cfg.tick != 0:
        return ReplaceDecision(ok=False, reason="INVALID_ORDER", keep_priority=False, new_leaves=0)

    # BUG: uses < instead of <=, allowing new_qty == cum_qty (leaves=0)
    if new_qty < order.cum_qty:
        return ReplaceDecision(
            ok=False, reason="INVALID_REPLACE", keep_priority=False, new_leaves=0
        )

    new_leaves = new_qty - order.cum_qty

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
