"""exchange_core/handlers/crash.py
Handle PRICE_CRASH: the PRICE_SHOCK margin waterfall plus the bankruptcy procedure after each
liquidation. Rule R-L0 (and R-W1 to R-W7). Reference only, not a task target.

Self-contained on purpose: it does not import handlers/shock.py, so the task f4_waterfall_b
(whose candidate replaces shock.py) cannot affect it.
"""
from exchange_core.book import get_account_orders, remove_order
from exchange_core.handlers.bankruptcy import handle_bankruptcy
from exchange_core.intmath import ceil_div
from exchange_core.types import Event, Report


def handle_crash(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Set the mark, run the waterfall, and run the bankruptcy procedure after each liquidation."""
    state = engine.state
    cfg = engine.cfg
    reports: list[Report] = [Report.mark_set(event.mark_price)]
    state.mark_price = event.mark_price

    for acc_id in sorted(a for a in state.accounts if a != "LIQ"):
        acc = state.accounts[acc_id]
        if acc.position == 0:
            continue
        req = ceil_div(abs(acc.position) * state.mark_price * cfg.maint_bps, 10_000)
        if acc.free_cash + acc.position * state.mark_price >= req:
            continue

        for o in get_account_orders(state, acc_id):
            remove_order(state, o.order_id)
            acc.locked_margin -= o.lock
            acc.free_cash += o.lock
            o.lock = 0
            reports.append(Report.cancelled(o.order_id, "RISK"))

        if acc.free_cash + acc.position * state.mark_price >= req:
            continue

        pre_position = acc.position
        liq = state.accounts["LIQ"]
        transfer = abs(pre_position) * state.mark_price
        if pre_position > 0:
            acc.free_cash += transfer
            liq.free_cash -= transfer
        else:
            acc.free_cash -= transfer
            liq.free_cash += transfer
        acc.position = 0
        liq.position += pre_position
        reports.append(Report.liquidated(acc_id, pre_position))

        # Rule R-L0: the bankruptcy procedure runs before the next account is examined
        reports.extend(handle_bankruptcy(engine, acc_id, pre_position))

    return reports
