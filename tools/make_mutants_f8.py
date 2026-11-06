# ruff: noqa: E501
"""tools/make_mutants_f8.py
Write the hand-designed mutants of the F8 reference (one bug each) to mutants/f8_adl_b/.
Each mutant is the reference with one text substitution.

    python tools/make_mutants_f8.py            # write the mutant files
    python tools/make_mutants_f8.py --expect   # also write each expect.toml from the grader
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
REF = (REPO_ROOT / "reference" / "f8_adl_b" / "bankruptcy.py").read_text(encoding="utf-8")
OUT = REPO_ROOT / "mutants" / "f8_adl_b"

IMPORT_LINE = "from exchange_core.types import Report\n"


def sub(old: str, new: str, text: str = REF) -> str:
    assert text.count(old) == 1, f"substitution target not unique/found: {old[:70]!r}"
    return text.replace(old, new, 1)


LIQUIDATE_HAIRCUT = '''    for acc_id in sorted(shares):
        if shares[acc_id] > 0:
            state.accounts[acc_id].free_cash -= shares[acc_id]
            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
            hit = state.accounts[acc_id]
            req = -(-abs(hit.position) * state.mark_price * 500 // 10_000)
            if hit.position != 0 and hit.free_cash + hit.position * state.mark_price < req:
                value = hit.position * state.mark_price
                hit.free_cash += value
                state.accounts["LIQ"].free_cash -= value
                state.accounts["LIQ"].position += hit.position
                reports.append(Report.liquidated(acc_id, hit.position))
                hit.position = 0
'''


def build() -> dict[str, tuple[str, str]]:
    m: dict[str, tuple[str, str]] = {}
    m["m_leftover_largest_remainder"] = (
        sub("ranked = sorted(weights, key=lambda a: (-weights[a], a))",
            "ranked = sorted(weights, key=lambda a: (-(remaining * weights[a] % total), a))"),
        "Leftover units go to the largest fractional remainders (the textbook method) instead of the largest weights.")
    m["m_shares_rounded_half_even"] = (
        sub("shares = {acc_id: remaining * w // total for acc_id, w in weights.items()}",
            "shares = {acc_id: round_half_even(remaining * w, total) for acc_id, w in weights.items()}",
            sub(IMPORT_LINE, "from exchange_core.intmath import round_half_even\n" + IMPORT_LINE)),
        "Each base share is rounded half to even instead of floored, so the shares can add up to more or less than the remaining loss.")
    m["m_ties_descending_id"] = (
        sub("key=lambda a: (-weights[a], a))", "key=lambda a: (-weights[a], [-ord(c) for c in a]))"),
        "Equal weights are sorted by descending account id.")
    m["m_leftover_ignores_weight"] = (
        sub("ranked = sorted(weights, key=lambda a: (-weights[a], a))", "ranked = sorted(weights)"),
        "Leftover units go to the lowest account ids, whatever their weight.")
    m["m_tie_numeric_id_order"] = (
        sub("key=lambda a: (-weights[a], a))", "key=lambda a: (-weights[a], int(a[1:])))"),
        "Equal weights are ordered by the number in the account id, so A2 comes before A10.")
    m["m_adl_reports_numeric_order"] = (
        sub("for acc_id in sorted(shares):", "for acc_id in sorted(shares, key=lambda a: int(a[1:])):"),
        "ADL_APPLIED reports (and payments) are ordered by the number in the account id.")
    m["m_same_side_eligible"] = (
        sub("if (acc.position > 0) != (pre_position > 0):", "if (acc.position > 0) == (pre_position > 0):"),
        "The accounts on the SAME side as the liquidated position pay the loss.")
    m["m_liq_eligible"] = (
        sub('if acc_id == "LIQ" or acc_id == account_id or acc.position == 0:', "if acc_id == account_id or acc.position == 0:"),
        "The LIQ account can be charged a loss share.")
    m["m_zero_position_eligible"] = (
        sub('if acc_id == "LIQ" or acc_id == account_id or acc.position == 0:', 'if acc_id == "LIQ" or acc_id == account_id:'),
        "Accounts with no position count as eligible (weight 0); with nobody else the total weight is 0.")
    m["m_insurance_skipped"] = (
        sub("cover = min(deficit, max(0, state.fee_vault))", "cover = 0"),
        "The fee vault is never used: the whole deficit goes to the loss sharing.")
    m["m_insurance_ignores_vault_limit"] = (
        sub("cover = min(deficit, max(0, state.fee_vault))", "cover = deficit"),
        "The insurance draw is not limited by the vault balance (the vault can go negative).")
    m["m_vault_not_decreased"] = (
        sub("        state.fee_vault -= cover\n", ""),
        "The insurance amount is credited to the account but not taken from the fee vault.")
    m["m_vault_not_floored"] = (
        sub("cover = min(deficit, max(0, state.fee_vault))", "cover = min(deficit, state.fee_vault)"),
        "The insurance draw is capped by the vault balance without a floor at 0: a negative vault adds to the amount shared among the other accounts.")
    m["m_zero_share_reported"] = (
        sub("        if shares[acc_id] > 0:", "        if shares[acc_id] >= 0:"),
        "An ADL_APPLIED report is also written for an account whose share is 0.")
    m["m_insurance_report_last"] = (
        sub("    victim.free_cash += remaining\n    return reports\n", "    victim.free_cash += remaining\n    return sorted(reports, key=lambda r: r.kind)\n"),
        "The reports are sorted by kind, so INSURANCE_DRAWN comes after the ADL_APPLIED reports.")
    m["m_bad_debt_not_reported"] = (
        sub('        reports.append(Report(kind="BAD_DEBT", account=account_id, qty=remaining))\n', "        pass\n"),
        "The BAD_DEBT report is not emitted when nobody can share the loss.")
    m["m_leftover_not_distributed"] = (
        sub("for acc_id in ranked[:leftover]:", "for acc_id in ranked[:leftover * 0]:"),
        "The leftover units are not handed out, so the payers pay less than the account receives (money is created).")
    m["m_leftover_off_by_one"] = (
        sub("for acc_id in ranked[:leftover]:", "for acc_id in ranked[:leftover + 1]:"),
        "One unit too many is handed out, so the payers pay more than the account receives (money is destroyed).")
    m["m_share_not_charged"] = (
        sub("            state.accounts[acc_id].free_cash -= shares[acc_id]\n", ""),
        "The ADL_APPLIED report is emitted but the share is not taken from the account (money is created).")
    m["m_victim_not_credited"] = (
        sub("    victim.free_cash += remaining\n    return reports\n", "    return reports\n"),
        "The loss shares are charged but the ruined account is not credited (money is destroyed).")
    m["m_liquidates_haircut_accounts"] = (
        sub('''    for acc_id in sorted(shares):
        if shares[acc_id] > 0:
            state.accounts[acc_id].free_cash -= shares[acc_id]
            reports.append(Report(kind="ADL_APPLIED", account=acc_id, qty=shares[acc_id]))
''', LIQUIDATE_HAIRCUT),
        "An account that falls below the maintenance requirement after its loss share is liquidated at once inside the procedure (the waterfall must do that, later, itself).")
    return m


def main() -> None:
    muts = build()
    for name, (code, why) in muts.items():
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "bankruptcy.py").write_text(code, encoding="utf-8")
        (d / "DESCRIPTION.txt").write_text(why + "\n", encoding="utf-8")
    print(f"wrote {len(muts)} mutants to {OUT}")
    if "--expect" in sys.argv:
        write_expect(muts)


def write_expect(muts: dict[str, tuple[str, str]]) -> None:
    import math

    from graders.dst_grader import grade_task

    for name, (code, _) in muts.items():
        rec = grade_task("f8_adl_b", {"exchange_core/handlers/bankruptcy.py": code}, is_candidate=True)
        assert not rec.passed, f"{name} is not caught by the grader"
        lines = ["[expect]", f"t1_min = {math.floor(rec.t1 * 100) / 100:.2f}",
                 f"t3_max = {math.ceil(rec.t3 * 100) / 100:.2f}"]
        if rec.first_failure:
            lines.append(f'violated = ["{rec.first_failure["invariant"]}"]')
        lines.append("passed = false")
        (OUT / name / "expect.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
        tier = "T1" if rec.t1 < 1 else "T2" if rec.t2 < 1 else "T3"
        print(f"  {name:<34} t1={rec.t1:.2f} t2={rec.t2:.2f} t3={rec.t3:.2f} first={tier} "
              f"inv={(rec.first_failure or {}).get('invariant')}")


if __name__ == "__main__":
    main()
