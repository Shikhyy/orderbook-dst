"""exchange_core/rules/waterfall_rule.py
Pure margin waterfall planning rule R-W2, R-W4.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import ceil_div
from exchange_core.types import AccountView, WaterfallPlan


def plan_waterfall(view: AccountView, mark: int, cfg: EngineConfig) -> WaterfallPlan:
    """Plan liquidation stages for an account under mark price.

    Rules R-W2, R-W4.
    """
    if view.position == 0:
        return WaterfallPlan(in_breach_stage1=False, in_breach_stage2=False)

    avail1 = view.free_cash + view.position * mark
    req = ceil_div(abs(view.position) * mark * cfg.maint_bps, 10_000)

    if avail1 >= req:
        return WaterfallPlan(in_breach_stage1=False, in_breach_stage2=False)

    # In breach at Stage 1: cancelling resting orders releases all locked margin
    free_cash_after_stage1 = view.free_cash + view.locked_margin
    avail2 = free_cash_after_stage1 + view.position * mark

    if avail2 >= req:
        return WaterfallPlan(
            in_breach_stage1=True,
            in_breach_stage2=False,
            liquidate_qty=0,
        )

    return WaterfallPlan(
        in_breach_stage1=True,
        in_breach_stage2=True,
        liquidate_qty=view.position,
    )
