"""exchange_core/rules/waterfall_rule.py
Pure function for margin waterfall breach calculation.
Rules R-W2, R-W4.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import ceil_div
from exchange_core.types import AccountView, WaterfallPlan


def plan_waterfall(view: AccountView, mark: int, cfg: EngineConfig) -> WaterfallPlan:
    """Evaluate whether an account breaches maintenance margin in stage 1 and stage 2.

    Rules R-W2, R-W4:
    - avail = free_cash + position * mark_price
    - req = ceil_div(abs(position) * mark_price * MAINT_BPS, 10000)
    - in_breach if avail < req (position == 0 is never in breach)
    """
    # Rule R-W2: position == 0 is never in breach
    if view.position == 0:
        return WaterfallPlan(
            in_breach_stage1=False,
            in_breach_stage2=False,
            liquidate_qty=0,
        )

    # Rule R-W2: breach calculation
    avail = view.free_cash + view.position * mark
    req = ceil_div(abs(view.position) * mark * cfg.maint_bps, 10_000)
    in_breach_stage1 = avail < req

    if not in_breach_stage1:
        return WaterfallPlan(
            in_breach_stage1=False,
            in_breach_stage2=False,
            liquidate_qty=0,
        )

    # Rule R-W4: stage 2 re-check with locks released to free_cash
    avail_stage2 = (view.free_cash + view.locked_margin) + view.position * mark
    in_breach_stage2 = avail_stage2 < req
    liquidate_qty = view.position if in_breach_stage2 else 0

    return WaterfallPlan(
        in_breach_stage1=True,
        in_breach_stage2=in_breach_stage2,
        liquidate_qty=liquidate_qty,
    )
