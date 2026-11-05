"""Bankruptcy procedure (clean-room version, written from the task text only)."""
from typing import Any

from exchange_core.types import Report


def handle_bankruptcy(engine: Any, account_id: str, pre_position: int) -> list[Report]:
    state = engine.state
    ruined = state.accounts[account_id]
    out: list[Report] = []

    deficit = -ruined.free_cash if ruined.free_cash < 0 else 0
    if deficit == 0:
        return out

    available = state.fee_vault if state.fee_vault > 0 else 0
    cover = deficit if deficit < available else available
    if cover > 0:
        state.fee_vault -= cover
        ruined.free_cash += cover
        out.append(Report(kind="INSURANCE_DRAWN", account=account_id, qty=cover))
    remaining = deficit - cover
    if remaining == 0:
        return out

    long_side = pre_position > 0
    pool = []  # (account id, weight)
    for acct_id, acct in state.accounts.items():
        if acct_id in ("LIQ", account_id) or acct.position == 0:
            continue
        if (acct.position > 0) == long_side:
            continue
        pool.append((acct_id, abs(acct.position)))

    if not pool:
        out.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))
        return out

    total_weight = sum(w for _, w in pool)
    share = {acct_id: (remaining * w) // total_weight for acct_id, w in pool}
    extra = remaining - sum(share.values())
    pool.sort(key=lambda item: (-item[1], item[0]))
    for acct_id, _ in pool[:extra]:
        share[acct_id] += 1

    for acct_id in sorted(share):
        amount = share[acct_id]
        if amount <= 0:
            continue
        state.accounts[acct_id].free_cash -= amount
        ruined.free_cash += amount
        out.append(Report(kind="ADL_APPLIED", account=acct_id, qty=amount))
    return out
