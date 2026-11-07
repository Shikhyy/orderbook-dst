"""exchange_core/handlers/funding.py
Handler for FUNDING events: funding payments, fee-vault residual and waterfall.
Rules R-Y1 to R-Y5. Target for task f7_funding_b.
"""
from exchange_core.types import Event, Report
from exchange_core.intmath import round_half_even


def handle_funding(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a FUNDING event."""
    state = engine.state
    cfg = engine.cfg

    # R-Y1: Clamp rate to [-3000, 3000]
    rate = max(-3000, min(3000, event.bps))

    reports: list[Report] = []
    n = 0  # number of accounts processed
    net_payment = 0  # payments minus receipts

    if rate != 0:
        # R-Y2: Process every account with position != 0 in ascending account-id order
        accounts_with_position = [
            (acc_id, acc) for acc_id, acc in state.accounts.items()
            if acc.position != 0
        ]
        accounts_with_position.sort(key=lambda x: x[0])  # sort by account_id ascending

        n = len(accounts_with_position)

        for acc_id, acc in accounts_with_position:
            notional = abs(acc.position) * state.mark_price
            amount = round_half_even(notional * abs(rate), cfg.ppm)

            is_long = acc.position > 0
            is_short = acc.position < 0

            # Pays when (long and rate > 0) or (short and rate < 0)
            pays = (is_long and rate > 0) or (is_short and rate < 0)

            if pays:
                acc.free_cash -= amount
                net_payment += amount
            else:
                acc.free_cash += amount
                net_payment -= amount

    # R-Y3: Add net of all payments to fee_vault
    state.fee_vault += net_payment

    # R-Y4: First report
    reports.append(Report(kind="FUNDING_APPLIED", bps=rate, qty=n))

    # R-Y5: Run margin waterfall via PRICE_SHOCK dispatch
    price_shock_event = Event(kind="PRICE_SHOCK", mark_price=state.mark_price)
    shock_reports = engine.dispatch(price_shock_event)
    reports.extend(shock_reports)

    return reports
