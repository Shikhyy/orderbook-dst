"""exchange_core/handlers/funding.py
Handler for FUNDING events: funding payments, fee-vault residual and waterfall.
Rules R-Y1 to R-Y5. Target for task f7_funding_b.
"""
from exchange_core.types import Event, Report
from exchange_core.intmath import round_half_even


def handle_funding(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a FUNDING event."""
    # R-Y1: Clamp rate
    rate = event.bps
    if rate < -3000:
        rate = -3000
    elif rate > 3000:
        rate = 3000

    reports = []
    net_payment = 0
    accounts_processed = 0

    if rate != 0:
        # R-Y2: Process accounts with position != 0 in ascending order
        account_ids = sorted(engine.state.accounts.keys())
        mark_price = engine.state.mark_price
        ppm = engine.cfg.ppm

        for acc_id in account_ids:
            account = engine.state.accounts[acc_id]
            if account.position != 0:
                accounts_processed += 1
                notional = abs(account.position) * mark_price
                amount = round_half_even(notional * abs(rate), ppm)

                # Determine if pay (subtract from free_cash) or receive (add to free_cash)
                # Long: position > 0. Short: position < 0.
                # Long + rate > 0: pay. Short + rate < 0: pay.
                # Otherwise: receive.
                is_long = account.position > 0
                is_paying = (is_long and rate > 0) or (not is_long and rate < 0)

                if is_paying:
                    account.free_cash -= amount
                    net_payment += amount
                else:
                    account.free_cash += amount
                    net_payment -= amount

        # R-Y3: Add net to fee_vault (net = payments - receipts)
        engine.state.fee_vault += net_payment

    # R-Y4: First report
    reports.append(Report(kind="FUNDING_APPLIED", bps=rate, qty=accounts_processed))

    # R-Y5: Run margin waterfall
    shock_event = Event(kind="PRICE_SHOCK", mark_price=engine.state.mark_price)
    reports.extend(engine.dispatch(shock_event))

    return reports
