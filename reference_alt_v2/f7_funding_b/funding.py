"""Funding payments handler."""
from typing import Any

from exchange_core.intmath import round_half_even
from exchange_core.types import Event, Report

RATE_LIMIT = 3000


def handle_funding(engine: Any, event: Event) -> list[Report]:
    state = engine.state
    ppm = engine.cfg.ppm
    rate = max(-RATE_LIMIT, min(RATE_LIMIT, event.bps))

    processed = 0
    net_paid = 0  # payments minus receipts
    if rate != 0:
        mark = state.mark_price
        for acct_id in sorted(a for a, acc in state.accounts.items() if acc.position != 0):
            acc = state.accounts[acct_id]
            notional = abs(acc.position) * mark
            amount = round_half_even(notional * abs(rate), ppm)
            is_long = acc.position > 0
            pays = (is_long and rate > 0) or (not is_long and rate < 0)
            if pays:
                acc.free_cash -= amount
                net_paid += amount
            else:
                acc.free_cash += amount
                net_paid -= amount
            processed += 1
        state.fee_vault += net_paid

    reports = [Report(kind="FUNDING_APPLIED", bps=rate, qty=processed)]
    reports.extend(
        engine.dispatch(Event(kind="PRICE_SHOCK", mark_price=state.mark_price))
    )
    return reports
