"""exchange_core/handlers/funding.py
Handler for FUNDING events: funding payments, fee-vault residual and waterfall.
Rules R-Y1 to R-Y5. Target for task f7_funding_b.
"""
from exchange_core.types import Event, Report
from exchange_core.state import EngineState
from exchange_core.intmath import round_half_even
from exchange_core.config import EngineConfig

def handle_funding(engine: "Engine", event: Event) -> list[Report]:
    """Process a FUNDING event."""
    state = engine.state
    cfg = engine.cfg
    rate = event.bps
    ppm = cfg.ppm

    # Rule R-Y1: Clamp the rate to the range -3000 to +3000
    rate = max(-3000, min(3000, rate))

    # Rule R-Y4: Create the first report
    accounts_processed = 0
    reports = []

    if rate != 0:
        # Rule R-Y2: Process each account with position != 0
        accounts = sorted(state.accounts.keys())
        for account_id in accounts:
            account = state.accounts[account_id]
            if account.position != 0:
                notional = abs(account.position) * state.mark_price
                amount = round_half_even(notional * abs(rate), ppm)

                # Determine if account pays or receives
                if (account.position > 0 and rate > 0) or (account.position < 0 and rate < 0):
                    # Account pays
                    state.accounts[account_id].free_cash -= amount
                else:
                    # Account receives
                    state.accounts[account_id].free_cash += amount
                accounts_processed += 1

    # Rule R-Y3: Add net of all payments to fee_vault
    net_payment = 0
    for account_id in state.accounts:
        account = state.accounts[account_id]
        if account.position != 0:
            notional = abs(account.position) * state.mark_price
            amount = round_half_even(notional * abs(rate), ppm)
            if (account.position > 0 and rate > 0) or (account.position < 0 and rate < 0):
                net_payment -= amount
            else:
                net_payment += amount
    state.fee_vault += net_payment

    # Rule R-Y4: Create the first report
    reports.append(Report(kind="FUNDING_APPLIED", bps=rate, qty=accounts_processed))

    # Rule R-Y5: Run the margin waterfall
    shock_reports = engine.dispatch(Event(kind="PRICE_SHOCK", mark_price=state.mark_price))
    reports.extend(shock_reports)

    return reports
