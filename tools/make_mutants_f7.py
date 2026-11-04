# ruff: noqa: E501
"""tools/make_mutants_f7.py
Write the hand-designed mutants of the F7 reference (one bug each) to mutants/f7_funding_b/.
Each mutant is the reference with exactly one text substitution.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
REF = (REPO_ROOT / "reference" / "f7_funding_b" / "funding.py").read_text(encoding="utf-8")
OUT = REPO_ROOT / "mutants" / "f7_funding_b"


DROP_IMPORT = "from exchange_core.intmath import round_half_even\n"


def sub(old: str, new: str, text: str = REF) -> str:
    assert text.count(old) == 1, f"substitution target not unique/found: {old[:60]!r}"
    return text.replace(old, new, 1)


def build() -> dict[str, tuple[str, str]]:
    m: dict[str, tuple[str, str]] = {}
    m["m_no_clamp"] = (
        sub("rate = max(-MAX_FUNDING_PPM, min(MAX_FUNDING_PPM, event.bps))", "rate = event.bps"),
        "The rate is not clamped to +/-3000.")
    m["m_sign_swapped"] = (
        sub("pays = (acc.position > 0) == (rate > 0)", "pays = (acc.position > 0) != (rate > 0)"),
        "Direction reversed: on a positive rate the shorts pay the longs.")
    m["m_residual_not_to_vault"] = (
        sub("    state.fee_vault += residual\n", "    pass\n"),
        "The rounding residual is dropped instead of being added to the fee vault.")
    m["m_half_up_rounding"] = (
        sub(DROP_IMPORT, "",
        sub("amount = round_half_even(notional * abs(rate), ppm)",
            "amount = (2 * notional * abs(rate) + ppm) // (2 * ppm)")),
        "Rounds half up instead of half to even.")
    m["m_floor_rounding"] = (
        sub(DROP_IMPORT, "",
        sub("amount = round_half_even(notional * abs(rate), ppm)",
            "amount = (notional * abs(rate)) // ppm")),
        "Floors the amount instead of rounding to nearest.")
    m["m_no_waterfall"] = (
        sub("    reports.extend(engine.dispatch(Event(kind=\"PRICE_SHOCK\", mark_price=state.mark_price)))\n", ""),
        "The margin waterfall is not run after funding.")
    m["m_waterfall_only_if_rate"] = (
        sub("    reports.extend(engine.dispatch(Event(kind=\"PRICE_SHOCK\", mark_price=state.mark_price)))\n",
            "    if rate != 0:\n        reports.extend(engine.dispatch(Event(kind=\"PRICE_SHOCK\", mark_price=state.mark_price)))\n"),
        "The waterfall is skipped when the rate is 0.")
    m["m_skips_liq"] = (
        sub("            if acc.position == 0:\n", "            if acc.position == 0 or acc_id == \"LIQ\":\n"),
        "The LIQ account is left out of the funding payments.")
    m["m_wrong_mark_in_waterfall"] = (
        sub("Event(kind=\"PRICE_SHOCK\", mark_price=state.mark_price)", "Event(kind=\"PRICE_SHOCK\", mark_price=event.mark_price)"),
        "The waterfall is dispatched with the funding event's own (unused, zero) mark price.")
    m["m_skips_negative_cash"] = (
        sub("            if acc.position == 0:\n", "            if acc.position == 0 or acc.free_cash < 0:\n"),
        "Accounts whose free_cash is already negative are skipped.")
    return m


def main() -> None:
    muts = build()
    for name, (code, why) in muts.items():
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "funding.py").write_text(code, encoding="utf-8")
        (d / "DESCRIPTION.txt").write_text(why + "\n", encoding="utf-8")
    print(f"wrote {len(muts)} mutants to {OUT}")


if __name__ == "__main__":
    main()
