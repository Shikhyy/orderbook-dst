"""exchange_core/handlers/bankruptcy.py"""
from exchange_core.types import Report


def handle_bankruptcy(engine: "Engine", account_id: str, pre_position: int) -> list[Report]:  # type: ignore # noqa: F821
    """Cover the negative cash of a just-liquidated account and return the reports."""
    state = engine.state
    victim = state.accounts[account_id]

    # Rule R-L1: the deficit is the negative cash that remains after liquidation
    deficit = max(0, -victim.free_cash)
    if deficit == 0:
        return []

    reports: list[Report] = []

    # Rule R-L2: the fee vault (never below zero) pays first
    cover = min(deficit, max(0, state.fee_vault))
    if cover > 0:
        state.fee_vault -= cover
        victim.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))

    remaining = deficit - cover
    if remaining == 0:
        return reports

    # Rule R-L3: the rest is shared by the accounts on the other side of the liquidated position
    weights: dict[str, int] = {}
    for acc_id, acc in state.accounts.items():
        if acc_id == "LIQ" or acc_id == account_id or acc.position == 0:
            continue
        if (acc.position > 0) != (pre_position > 0):
            weights[acc_id] = abs(acc.position)

    # Rule R-L4: nobody to share with, the loss stays as bad debt
    if not weights:
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    total = sum(weights.values())
    shares = {acc_id: remaining * w // total for acc_id, w in weights.items()}
    leftover = remaining - sum(shares.values())
    
    # Sort eligible accounts by descending weight; accounts with same weight by ascending account id
    # leftover accounts get +1 unit, using the sort order described
    ranked = sorted(weights.keys(), key=lambda a: (-weights[a], a))
    for i in range(leftover):
        shares[ranked[i]] += 1

    for acc_id in sorted(shares.keys()):
        if shares[acc_id] > 0:
            state.accounts[acc_id].free_cash -= shares[acc_id]
            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
    
    victim.free_cash += remaining
    return reports
