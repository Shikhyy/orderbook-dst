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
    deficit = max(0, -account.free_cash)
    if deficit == 0:
        return []

    reports = []
    
    # R-L2: Fee vault pays first
    cover = min(deficit, max(0, state.fee_vault))
    remaining = deficit
    if cover > 0:
        state.fee_vault -= cover
        account.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
        remaining -= cover
    
    if remaining == 0:
        return reports

    # R-L3: Loss sharing among eligible accounts
    # Eligible: not LIQ, not account_id, position != 0, opposite sign to pre_position
    eligible = []
    for aid, acc in state.accounts.items():
        if aid == "LIQ" or aid == account_id:
            continue
        if acc.position != 0 and (
            (pre_position > 0 and acc.position < 0) or 
            (pre_position < 0 and acc.position > 0)
        ):
            eligible.append((aid, abs(acc.position)))
    
    if not eligible:
        # R-L4: No eligible accounts
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    total_weight = sum(w for _, w in eligible)
    
    # Calculate initial shares
    shares = {aid: (remaining * w) // total_weight for aid, w in eligible}
    distributed = sum(shares.values())
    leftover = remaining - distributed
    
    # Sort for leftover distribution: descending weight, ascending account ID
    eligible.sort(key=lambda x: (-x[1], x[0]))
    for i in range(leftover):
        aid = eligible[i][0]
        shares[aid] += 1
        
    # Apply shares
    for aid, share in shares.items():
        if share > 0:
            state.accounts[aid].free_cash -= share
            
    account.free_cash += remaining
    
    # Sort reports by account id for consistent output
    sorted_eligible_ids = sorted([aid for aid, share in shares.items() if share > 0])
    for aid in sorted_eligible_ids:
        reports.append(Report(kind="ADL_APPLIED", account=aid, qty=shares[aid]))
        
    return reports
