"""Price shock and margin waterfall handler (Task f4_waterfall_b).

Rules:
- R-W1: Set mark_price and run waterfall for each account except LIQ in ascending account ID order.
- R-W2: Availability and maintenance margin requirement.
- R-W3: Stage 1 resting order cancellation.
- R-W4: Recheck after stage 1.
- R-W5: Stage 2 liquidation against LIQ.
- R-W6: Report ordering (MARK_SET, stage 1 cancels, LIQUIDATED).
- R-W7: Lexicographical account ordering.
"""
from typing import Any

from exchange_core.book import get_account_orders, remove_order
from exchange_core.intmath import ceil_div
from exchange_core.ledger import adjust_position, get_account, release_lock, transfer_cash
from exchange_core.rules.waterfall_rule import plan_waterfall
from exchange_core.types import AccountView, Event, Report


def handle_shock(engine: Any, event: Event) -> list[Report]:
    """Handle a PRICE_SHOCK event and run margin waterfall.

    Rules R-W1 to R-W7:
    - Set mark_price.
    - First report: MARK_SET.
    - Iterate accounts except LIQ in ascending lexicographical order (R-W7).
    - For each account:
        - Check breach (R-W2).
        - Stage 1: if in breach, cancel all resting orders in prio_seq order,
          releasing lock and reporting CANCELLED(order_id, RISK).
        - Stage 2: recheck breach with new free_cash (R-W4). If still in breach,
          liquidate entire position against LIQ at mark_price (R-W5),
          reporting LIQUIDATED(account, signed_qty).
    """
    engine.state.mark_price = event.mark_price
    reports = [Report.mark_set(event.mark_price)]

    # R-W1, R-W7: Ascending lexicographical order of account IDs, excluding LIQ
    account_ids = sorted([aid for aid in engine.state.accounts.keys() if aid != "LIQ"])

    for acc_id in account_ids:
        acc = get_account(engine.state, acc_id)
        if acc is None or acc.position == 0:
            continue

        view = AccountView(
            account_id=acc_id,
            free_cash=acc.free_cash,
            locked_margin=acc.locked_margin,
            position=acc.position,
        )
        plan = plan_waterfall(view, event.mark_price, engine.cfg)

        if not plan.in_breach_stage1:
            continue

        # Stage 1: cancel all resting orders of the account in ascending prio_seq order
        orders = get_account_orders(engine.state, acc_id)
        for order in orders:
            remove_order(engine.state, order.order_id)
            release_lock(engine.state, acc_id, order.lock)
            order.lock = 0
            reports.append(Report.cancelled(order.order_id, "RISK"))

        # Stage 2: recheck breach after stage 1 cancels (R-W4, R-W5)
        avail = acc.free_cash + acc.position * event.mark_price
        req = ceil_div(abs(acc.position) * event.mark_price * engine.cfg.maint_bps, 10000)
        if avail < req:
            pos = acc.position
            notional = abs(pos) * event.mark_price

            if pos > 0:
                # Account sells pos to LIQ: LIQ pays notional to account
                transfer_cash(engine.state, "LIQ", acc_id, notional)
                adjust_position(engine.state, acc_id, -pos)
                adjust_position(engine.state, "LIQ", pos)
            else:
                # Account buys abs(pos) from LIQ: account pays notional to LIQ
                transfer_cash(engine.state, acc_id, "LIQ", notional)
                adjust_position(engine.state, acc_id, -pos)
                adjust_position(engine.state, "LIQ", pos)

            reports.append(Report.liquidated(acc_id, pos))

    return reports
