"""exchange_core/handlers/funding.py
Handler for FUNDING events: funding payments, fee-vault residual and waterfall.
Rules R-Y1 to R-Y5. Target for task f7_funding_b.
"""
from exchange_core.intmath import round_half_even
from exchange_core.types import Event, Report


def handle_funding(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a FUNDING event."""
    state = engine.state
    ppm = engine.cfg.ppm

    # R-Y1: clamp the funding rate to [-3000, 3000].
    rate = max(-3000, min(3000, event.bps))

    total_paid = 0
    total_received = 0
    n = 0

    # R-Y2: if rate != 0, process every account with a non-zero position,
    # in ascending account-id order.
    if rate != 0:
        mark_price = state.mark_price
        for account_id in sorted(state.accounts):
            account = state.accounts[account_id]
            if account.position == 0:
                continue

            n += 1
            notional = abs(account.position) * mark_price
            amount = round_half_even(notional * abs(rate), ppm)

            pays = (account.position > 0 and rate > 0) or (
                account.position < 0 and rate < 0
            )
            if pays:
                account.free_cash -= amount
                total_paid += amount
            else:
                account.free_cash += amount
                total_received += amount

    # R-Y3: book the net rounding difference in the fee vault.
    state.fee_vault += total_paid - total_received

    # R-Y4: first report is FUNDING_APPLIED.
    reports = [Report(kind="FUNDING_APPLIED", bps=rate, qty=n)]

    # R-Y5: always run the margin waterfall at the current mark price.
    reports.extend(
        engine.dispatch(Event(kind="PRICE_SHOCK", mark_price=state.mark_price))
    )

    return reports
