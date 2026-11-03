"""Margin waterfall planning rules.

Rules:
- R-W2: Breach check for position != 0:
    avail = free_cash + position * mark
    req = ceil_div(abs(position) * mark * cfg.maint_bps, 10000)
    in_breach = avail < req
    (Account with position == 0 is never in breach).
- R-W3: Stage 1 cancels all resting orders if in breach.
- R-W4: Recheck after stage 1 (avail with locked_margin released to free_cash).
- R-W5: Stage 2 liquidation if still in breach.
"""
from exchange_core.config import EngineConfig
from exchange_core.intmath import ceil_div
from exchange_core.types import AccountView, WaterfallPlan


def plan_waterfall(view: AccountView, mark: int, cfg: EngineConfig) -> WaterfallPlan:
    """Plan margin waterfall for an account.

    Returns a WaterfallPlan indicating whether stage 1 and stage 2 breaches occur,
    and the signed quantity to liquidate if stage 2 is needed.
    """
    if view.position == 0:
        return WaterfallPlan(
            in_breach_stage1=False,
            in_breach_stage2=False,
            cancelled_orders=[],
            liquidate_qty=0,
        )

    # Initial breach check (Stage 1)
    avail1 = view.free_cash + view.position * mark
    req = ceil_div(abs(view.position) * mark * cfg.maint_bps, 10000)
    in_breach_1 = avail1 < req

    if not in_breach_1:
        return WaterfallPlan(
            in_breach_stage1=False,
            in_breach_stage2=False,
            cancelled_orders=[],
            liquidate_qty=0,
        )

    # Recheck after hypothetical Stage 1 cancel (releasing all locked_margin)
    avail2 = (view.free_cash + view.locked_margin) + view.position * mark
    in_breach_2 = avail2 < req

    liquidate_qty = view.position if in_breach_2 else 0

    return WaterfallPlan(
        in_breach_stage1=True,
        in_breach_stage2=in_breach_2,
        cancelled_orders=[],
        liquidate_qty=liquidate_qty,
    )
