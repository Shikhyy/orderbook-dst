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

    # R-L1: no deficit means no change and no report.
    deficit = max(0, -account.free_cash)
    if deficit == 0:
        return []

    reports: list[Report] = []

    # R-L2: the fee vault pays first.
    cover = min(deficit, max(0, state.fee_vault))
    if cover > 0:
        state.fee_vault -= cover
        account.free_cash += cover
        reports.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))

    remaining = deficit - cover
    if remaining == 0:
        return reports

    # R-L3: eligible accounts are on the other side of the liquidated position.
    eligible: list[tuple[str, int]] = []
    for other_id, other in state.accounts.items():
        if other_id == "LIQ" or other_id == account_id:
            continue
        if other.position == 0:
            continue
        if (pre_position > 0 and other.position < 0) or (
            pre_position < 0 and other.position > 0
        ):
            eligible.append((other_id, abs(other.position)))

    if not eligible:
        # R-L4: the uncovered deficit remains as bad debt.
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    total_weight = sum(weight for _, weight in eligible)
    shares: dict[str, int] = {}
    distributed = 0

    for other_id, weight in eligible:
        base = remaining * weight // total_weight
        shares[other_id] = base
        distributed += base

    leftover = remaining - distributed

    # Largest weight first; ties are broken by ascending account id.
    by_weight = sorted(eligible, key=lambda item: (-item[1], item[0]))
    for index in range(leftover):
        other_id = by_weight[index][0]
        shares[other_id] += 1

    for other_id, share in shares.items():
        if share > 0:
            state.accounts[other_id].free_cash -= share

    account.free_cash += remaining

    # R-L5: ADL reports are in ascending account-id order.
    for other_id in sorted(shares):
        share = shares[other_id]
        if share > 0:
            reports.append(Report(kind="ADL_APPLIED", account=other_id, qty=share))

    return reports
