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
    reports: list[Report] = []

    # R-L1: Calculate deficit
    account = state.accounts[account_id]
    deficit = max(0, -account.free_cash)
    if deficit == 0:
        return reports

    # R-L2: Fee vault pays first
    cover = min(deficit, max(0, state.fee_vault))
    if cover > 0:
        state.fee_vault -= cover
        account.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))

    remaining = deficit - cover
    if remaining == 0:
        return reports

    # R-L3: Find eligible accounts on the other side
    # Eligible: not LIQ, not X, position != 0, sign(position) opposite to sign(pre_position)
    eligible: list[tuple[str, int]] = []  # (account_id, weight)
    pre_sign = 1 if pre_position > 0 else -1 if pre_position < 0 else 0

    for acc_id, acc in state.accounts.items():
        if acc_id == "LIQ" or acc_id == account_id:
            continue
        pos = acc.position
        if pos == 0:
            continue
        pos_sign = 1 if pos > 0 else -1
        if pos_sign != -pre_sign:  # opposite sign
            continue
        weight = abs(pos)
        eligible.append((acc_id, weight))

    if not eligible:
        # R-L4: No eligible accounts, bad debt
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    # Calculate base shares
    total_weight = sum(w for _, w in eligible)
    base_shares: dict[str, int] = {}
    sum_base = 0
    for acc_id, weight in eligible:
        base = remaining * weight // total_weight
        base_shares[acc_id] = base
        sum_base += base

    leftover = remaining - sum_base

    # Sort eligible by descending weight, then ascending account_id
    eligible_sorted = sorted(eligible, key=lambda x: (-x[1], x[0]))

    # First `leftover` accounts get +1
    final_shares: dict[str, int] = {}
    for i, (acc_id, _) in enumerate(eligible_sorted):
        share = base_shares[acc_id]
        if i < leftover:
            share += 1
        final_shares[acc_id] = share

    # Apply shares: each eligible account pays from free_cash
    for acc_id, share in final_shares.items():
        if share > 0:
            state.accounts[acc_id].free_cash -= share

    # X's free_cash increases by remaining
    account.free_cash += remaining

    # Report ADL_APPLIED in ascending account_id order for accounts with share > 0
    for acc_id in sorted(final_shares.keys()):
        share = final_shares[acc_id]
        if share > 0:
            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=share))

    return reports
