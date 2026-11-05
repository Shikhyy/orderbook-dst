"""tools/make_mutants_f6.py
Write the hand-designed mutants of the F6 reference (one bug each) to mutants/f6_match_b/.

Each mutant is the reference with exactly one text substitution, so the bug is
the only difference. expect.toml is written by tools/make_mutants_f6.py --expect
after measuring the grader's verdicts; those values then act as regression expectations.
"""
# ruff: noqa: E501
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
REF = (REPO_ROOT / "reference" / "f6_match_b" / "new_limit.py").read_text(encoding="utf-8")
OUT = REPO_ROOT / "mutants" / "f6_match_b"

PRICE_BLOCK = '''        # Check price crossing condition
        if order.side == "BUY" and best_resting.price > order.price:
            break
        if order.side == "SELL" and best_resting.price < order.price:
            break

'''
STP_BLOCK_END = '''            reports.append(Report.cancelled(best_resting.order_id, "STP"))
            continue

'''


def sub(old: str, new: str, text: str = REF) -> str:
    assert text.count(old) == 1, f"substitution target not unique/found: {old[:60]!r}"
    return text.replace(old, new, 1)


def build() -> dict[str, tuple[str, str]]:
    m: dict[str, tuple[str, str]] = {}
    m["m_no_stp"] = (
        sub("        if best_resting.account == order.account:", "        if False:"),
        "Self-trade prevention removed: an account trades with its own resting orders.")
    m["m_stp_lock_not_released"] = (
        sub('''            state.accounts[best_resting.account].locked_margin -= best_resting.lock
            state.accounts[best_resting.account].free_cash += best_resting.lock
''', ""),
        "STP cancels the resting order but leaves its margin locked.")
    m["m_fill_at_taker_price"] = (
        sub("fill_price = best_resting.price", "fill_price = order.price"),
        "The fill price is the incoming order's limit, not the resting price.")
    m["m_maker_lock_stale"] = (
        sub("        best_resting.lock = maker_new_lock\n",
            "        if best_resting.leaves == 0:\n            best_resting.lock = maker_new_lock\n"),
        "A partially filled resting order keeps its old stored lock (cash moves, lock field does not).")
    m["m_margin_default_rate"] = (
        sub("state.margin_bps, 10_000)\n    if acc.free_cash < lock",
            "cfg.margin_bps_default, 10_000)\n    if acc.free_cash < lock"),
        "The new order's lock uses the default margin rate instead of the current engine rate.")
    m["m_relock_current_rate"] = (
        sub("best_resting.leaves * best_resting.price * best_resting.margin_bps",
            "best_resting.leaves * best_resting.price * state.margin_bps"),
        "After a partial fill the resting order's lock is recomputed with the current engine "
        "margin rate instead of the rate stored in the order.")
    stp_at = sub(PRICE_BLOCK, "")
    m["m_stp_ignores_price"] = (
        sub(STP_BLOCK_END, STP_BLOCK_END + PRICE_BLOCK, stp_at),
        "STP is tested before the price test, so an own resting order that does not cross is cancelled.")
    m["m_post_only_ignores_own"] = (
        sub("add_order, best_ask, best_bid, get_asks", "add_order, get_asks",
            sub("        ask, bid = best_ask(state), best_bid(state)",
            "        ask = min((o.price for o in get_asks(state) if o.account != event.account), "
            "default=None)\n"
            "        bid = max((o.price for o in get_bids(state) if o.account != event.account), "
            "default=None)")),
        "POST_ONLY crossing test ignores the account's own resting orders.")
    m["m_stp_stops_matching"] = (
        sub(STP_BLOCK_END, '''            reports.append(Report.cancelled(best_resting.order_id, "STP"))
            break

'''),
        "After an STP cancellation matching stops instead of continuing with the next resting order.")
    m["m_ioc_lock_kept"] = (
        sub("        remaining_lock = order.lock\n", "        remaining_lock = 0\n"),
        "An IOC remainder is cancelled but its lock is not released.")
    m["m_filled_taker_rests"] = (
        sub('    elif order.flag != "IOC" and order.leaves > 0:', '    elif order.flag != "IOC":'),
        "A completely filled incoming order is stored in the book with leaves 0.")
    return m


def main() -> None:
    muts = build()
    for name, (code, why) in muts.items():
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "new_limit.py").write_text(code, encoding="utf-8")
        (d / "DESCRIPTION.txt").write_text(why + "\n", encoding="utf-8")
    print(f"wrote {len(muts)} mutants to {OUT}")


if __name__ == "__main__":
    main()
