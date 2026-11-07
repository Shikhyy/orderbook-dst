"""exchange_core/handlers/bankruptcy.py
Bankruptcy procedure after a liquidation: insurance draw, then loss sharing.
Rules R-L1 to R-L5. Target for task f8_adl_b.
"""
from exchange_core.types import Report


def handle_bankruptcy(
    engine: "Engine", account_id: str, pre_position: int  # type: ignore # noqa: F821
) -> list[Report]:
    """Cover the deficit of a just-liquidated account and return the reports in order."""
    state = engine.state
    account = state.accounts[account_id]
    
    reports: list[Report] = []
    
    # R-L1: Calculate deficit
    deficit = max(0, -account.free_cash)
    if deficit == 0:
        return []
    
    # R-L2: Fee vault pays first
    cover = min(deficit, max(0, state.fee_vault))
    if cover > 0:
        state.fee_vault -= cover
        account.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
    
    remaining = deficit - cover
    if remaining == 0:
        return reports
    
    # R-L3: Find eligible accounts
    # Eligible: not LIQ, not X, position != 0, position sign opposite to pre_position
    eligible = []
    for acc_id, acc in state.accounts.items():
        if acc_id == "LIQ" or acc_id == account_id:
            continue
        if acc.position == 0:
            continue
        # Check if position has opposite sign to pre_position
        if (pre_position > 0 and acc.position < 0) or (pre_position < 0 and acc.position > 0):
            weight = abs(acc.position)
            eligible.append((acc_id, acc, weight))
    
    if not eligible:
        # R-L4: No eligible accounts, bad debt
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports
    
    # Calculate shares
    total_weight = sum(w for _, _, w in eligible)
    
    # First calculate base shares
    shares: dict[str, int] = {}
    for acc_id, _, weight in eligible:
        base = (remaining * weight) // total_weight
        shares[acc_id] = base
    
    # Calculate leftover
    sum_base = sum(shares.values())
    leftover = remaining - sum_base
    
    # Sort eligible by descending weight, then ascending account_id for leftover distribution
    sorted_for_leftover = sorted(eligible, key=lambda x: (-x[2], x[0]))
    
    # Distribute leftover
    for i in range(leftover):
        acc_id, _, _ = sorted_for_leftover[i]
        shares[acc_id] += 1
    
    # Apply shares: each eligible account pays from free_cash
    # X's free_cash increases by remaining
    for acc_id, share in shares.items():
        if share > 0:
            state.accounts[acc_id].free_cash -= share
    
    account.free_cash += remaining
    
    # Generate ADL_APPLIED reports in ascending account-id order
    for acc_id in sorted(shares.keys()):
        share = shares[acc_id]
        if share > 0:
            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))
    
    return reports
