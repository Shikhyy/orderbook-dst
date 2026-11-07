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

    reports = []
    n_processed = 0

    if rate != 0:
        # R-Y2: Process accounts with position != 0 in ascending account-id order
        accounts_to_process = sorted(
            [(aid, acc) for aid, acc in state.accounts.items() if acc.position != 0],
            key=lambda x: x[0]
        )

        net_payment = 0  # payments - receipts

        for account_id, account in accounts_to_process:
            n_processed += 1
            position = account.position
            notional = abs(position) * state.mark_price
            amount = round_half_even(notional * abs(rate), cfg.ppm)

            # Pays when: long and rate > 0, or short and rate < 0
            pays = (position > 0 and rate > 0) or (position < 0 and rate < 0)

            if pays:
                account.free_cash -= amount
                net_payment += amount
            else:
                account.free_cash += amount
                net_payment -= amount

        # R-Y3: Add net payment to fee_vault
        state.fee_vault += net_payment

    # R-Y4: First report
    reports.append(Report(kind="FUNDING_APPLIED", bps=rate, qty=n_processed))

    # R-Y5: Dispatch PRICE_SHOCK event (margin waterfall)
    shock_event = Event(kind="PRICE_SHOCK", mark_price=state.mark_price)
    shock_reports = engine.dispatch(shock_event)
    reports.extend(shock_reports)

    return reports
