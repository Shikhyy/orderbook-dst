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

    reports: list[Report] = []

    # R-L2: fee vault pays first.
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
    for aid, acc in state.accounts.items():
        if aid == "LIQ" or aid == account_id:
            continue
        if acc.position == 0:
            continue
        if pre_position > 0 and acc.position < 0:
            eligible.append((aid, abs(acc.position)))
        elif pre_position < 0 and acc.position > 0:
            eligible.append((aid, abs(acc.position)))

    if not eligible:
        # R-L4: nobody can share the remaining deficit.
        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return reports

    total = sum(weight for _, weight in eligible)
    shares: dict[str, int] = {}
    for aid, weight in eligible:
        shares[aid] = remaining * weight // total

    leftover = remaining - sum(shares.values())
    if leftover > 0:
        # Descending weight, then ascending account id for ties.
        ordered = sorted(eligible, key=lambda item: (-item[1], item[0]))
        for aid, _ in ordered[:leftover]:
            shares[aid] += 1

    for aid, share in shares.items():
        state.accounts[aid].free_cash -= share

    account.free_cash += remaining

    # R-L5: ADL reports in ascending account-id order, only for positive shares.
    for aid in sorted(shares):
        share = shares[aid]
        if share > 0:
            reports.append(Report(kind="ADL_APPLIED", account=aid, qty=share))

    return reports
