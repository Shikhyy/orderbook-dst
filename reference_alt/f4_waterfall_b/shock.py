"""exchange_core/handlers/shock.py
Handle PRICE_SHOCK event.
Rules R-W1, R-W2, R-W3, R-W4, R-W5, R-W6.
"""
from typing import Any

from exchange_core.book import get_account_orders, remove_order
from exchange_core.config import EngineConfig
from exchange_core.intmath import ceil_div
from exchange_core.ledger import adjust_position, release_lock, transfer_cash
from exchange_core.types import AccountView, Event, Report, WaterfallPlan

# --- Rule logic (waterfall_rule), written out here because Variant B code may not
# import exchange_core.rules.* (see the task's 'Allowed imports'). ---

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


def handle_shock(engine: Any, event: Event) -> list[Report]:
    """Handle PRICE_SHOCK event and execute margin waterfall.

    Rules R-W1 to R-W6.
    """
    engine.state.mark_price = event.mark_price
    reports: list[Report] = [Report.mark_set(event.mark_price)]

    # Process all accounts except LIQ in ascending account_id order (Rule R-W1)
    account_ids = sorted([acc_id for acc_id in engine.state.accounts if acc_id != "LIQ"])

    for acc_id in account_ids:
        acc = engine.state.accounts[acc_id]
        if acc.position == 0:
            continue

        view = AccountView(
            account_id=acc_id,
            free_cash=acc.free_cash,
            locked_margin=acc.locked_margin,
            position=acc.position,
        )
        plan = plan_waterfall(view, event.mark_price, engine.cfg)

        if plan.in_breach_stage1:
            # Stage 1: cancel all resting orders in ascending prio_seq order
            orders = get_account_orders(engine.state, acc_id)
            for order in orders:
                remove_order(engine.state, order.order_id)
                release_lock(engine.state, acc_id, order.lock)
                order.lock = 0
                reports.append(Report.cancelled(order.order_id, "RISK"))

            # Stage 2: liquidate against LIQ if still in breach
            if plan.in_breach_stage2:
                qty = acc.position
                notional = abs(qty) * event.mark_price
                if qty > 0:
                    # Account sells position to LIQ
                    transfer_cash(engine.state, "LIQ", acc_id, notional)
                    adjust_position(engine.state, acc_id, -qty)
                    adjust_position(engine.state, "LIQ", qty)
                else:
                    # Account buys abs(position) from LIQ
                    transfer_cash(engine.state, acc_id, "LIQ", notional)
                    adjust_position(engine.state, acc_id, -qty)
                    adjust_position(engine.state, "LIQ", qty)

                reports.append(Report.liquidated(acc_id, qty))

    return reports
