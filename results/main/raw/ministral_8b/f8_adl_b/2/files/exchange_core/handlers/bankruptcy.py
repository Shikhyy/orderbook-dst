"""exchange_core/handlers/bankruptcy.py
Bankruptcy procedure after a liquidation: insurance draw, then loss sharing.
Rules R-L1 to R-L5. Target for task f8_adl_b.
"""
from exchange_core.types import Report
from exchange_core.state import EngineState
from exchange_core.ledger import get_account, transfer_cash
from exchange_core.intmath import round_half_even

def handle_bankruptcy(engine: "Engine", account_id: str, pre_position: int) -> list[Report]:
    """Cover the deficit of a just-liquidated account and return the reports in order."""
    state: EngineState = engine.state
    reports = []

    # Rule R-L1: Calculate deficit
    account = get_account(state, account_id)
    if account is None:
        return reports

    deficit = max(0, -account.free_cash)
    if deficit == 0:
        return reports

    # Rule R-L2: Cover from fee vault
    cover = min(deficit, max(0, state.fee_vault))
    if cover > 0:
        state.fee_vault -= cover
        account.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
        remaining = deficit - cover
    else:
        remaining = deficit

    if remaining == 0:
        return reports

    # Rule R-L3: Find eligible accounts
    eligible_accounts = []
    for acc_id, acc in state.accounts.items():
        if acc_id == account_id or acc_id == "LIQ" or acc.position == 0:
            continue
        if (acc.position > 0 and pre_position < 0) or (acc.position < 0 and pre_position > 0):
            eligible_accounts.append((acc_id, abs(acc.position)))

    if not eligible_accounts:
        # Rule R-L4: Bad debt
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    # Calculate total weight and base share
    total_weight = sum(weight for _, weight in eligible_accounts)
    if total_weight == 0:
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    # Sort eligible accounts by descending weight, then ascending account_id
    eligible_accounts.sort(key=lambda x: (-x[1], x[0]))

    # Calculate base share for each eligible account
    shares = []
    for acc_id, weight in eligible_accounts:
        base = remaining * weight // total_weight
        shares.append((acc_id, base))

    # Distribute leftover units
    leftover = remaining
    for acc_id, base in shares:
        leftover -= base

    # Sort accounts by descending weight, ascending account_id for tie-breaker
    eligible_accounts.sort(key=lambda x: (-x[1], x[0]))
    for i, (acc_id, _) in enumerate(eligible_accounts):
        if i < leftover:
            shares[i] = (acc_id, shares[i][1] + 1)

    # Apply shares and generate reports
    for acc_id, share in shares:
        if share > 0:
            transfer_cash(state, acc_id, account_id, share)
            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))

    # Update account free cash
    account.free_cash += remaining

    return reports
