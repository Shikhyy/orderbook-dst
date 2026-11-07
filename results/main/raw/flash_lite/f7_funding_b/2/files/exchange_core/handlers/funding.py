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
    num_accounts_processed = 0

    if rate != 0:
        # R-Y2: Process accounts with position != 0
        sorted_account_ids = sorted(engine.state.accounts.keys())
        net_payment = 0
        ppm = engine.cfg.ppm
        mark_price = engine.state.mark_price

        for acc_id in sorted_account_ids:
            account = engine.state.accounts[acc_id]
            if account.position != 0:
                num_accounts_processed += 1
                notional = abs(account.position) * mark_price
                amount = round_half_even(notional * abs(rate), ppm)

                # R-Y2: Payment/Receipt logic
                # Pay if (Long and rate > 0) or (Short and rate < 0)
                # Receive otherwise
                is_long = account.position > 0
                is_short = account.position < 0
                
                pays = (is_long and rate > 0) or (is_short and rate < 0)

                if pays:
                    account.free_cash -= amount
                    net_payment += amount
                else:
                    account.free_cash += amount
                    net_payment -= amount

        # R-Y3: Adjust fee vault
        engine.state.fee_vault += net_payment

    # R-Y4: Report FUNDING_APPLIED
    reports.append(Report(kind="FUNDING_APPLIED", bps=rate, qty=num_accounts_processed))

    # R-Y5: Run margin waterfall
    shock_event = Event(kind="PRICE_SHOCK", mark_price=engine.state.mark_price)
    reports.extend(engine.dispatch(shock_event))

    return reports
