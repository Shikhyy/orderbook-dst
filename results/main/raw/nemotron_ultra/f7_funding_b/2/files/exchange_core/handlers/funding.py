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
    processed_count = 0
    net_payment = 0  # payments minus receipts

    if rate != 0:
        # R-Y2: Process accounts with position != 0 in ascending account-id order
        accounts_to_process = sorted(
            [(aid, acc) for aid, acc in state.accounts.items() if acc.position != 0],
            key=lambda x: x[0]
        )

        mark_price = state.mark_price
        ppm = cfg.ppm
        abs_rate = abs(rate)

        for account_id, account in accounts_to_process:
            notional = abs(account.position) * mark_price
            amount = round_half_even(notional * abs_rate, ppm)

            is_long = account.position > 0
            is_short = account.position < 0

            # Account pays when (long and rate > 0) or (short and rate < 0)
            pays = (is_long and rate > 0) or (is_short and rate < 0)

            if pays:
                account.free_cash -= amount
                net_payment += amount
            else:
                account.free_cash += amount
                net_payment -= amount

            processed_count += 1

        # R-Y3: Net rounding difference to fee_vault
        state.fee_vault += net_payment

    # R-Y4: First report
    reports.append(Report(kind="FUNDING_APPLIED", bps=rate, qty=processed_count))

    # R-Y5: Run margin waterfall via PRICE_SHOCK
    shock_event = Event(kind="PRICE_SHOCK", mark_price=state.mark_price)
    shock_reports = engine.dispatch(shock_event)
    reports.extend(shock_reports)

    return reports
