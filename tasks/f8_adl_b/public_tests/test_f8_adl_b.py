"""tasks/f8_adl_b/public_tests/test_f8_adl_b.py
Public unit tests for task f8_adl_b.
"""
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.handlers.bankruptcy import handle_bankruptcy
from exchange_core.types import Event

P = 100_000_000
IDS = ["A1", "A2", "A3", "A10", "A11", "LIQ"]


def make(cash: dict, positions: dict, vault: int = 0) -> Engine:
    """An engine whose accounts are set directly (no trading)."""
    eng = Engine(EngineConfig(), {a: 0 for a in IDS}, mark_price=P)
    for acc, value in cash.items():
        eng.state.accounts[acc].free_cash = value
    for acc, value in positions.items():
        eng.state.accounts[acc].position = value
    eng.state.fee_vault = vault
    return eng


def view(eng):
    return {a: (v.free_cash, v.position) for a, v in eng.state.accounts.items()}


def test_no_deficit_changes_nothing():
    eng = make({"A1": 5_000}, {})
    before = view(eng)
    assert handle_bankruptcy(eng, "A1", 3) == []
    assert view(eng) == before and eng.state.fee_vault == 0


def test_vault_covers_the_whole_deficit():
    eng = make({"A1": -50}, {}, vault=80)
    reps = handle_bankruptcy(eng, "A1", 3)
    assert [(r.kind, r.account, r.qty) for r in reps] == [("INSURANCE_DRAWN", "A1", 50)]
    assert eng.state.accounts["A1"].free_cash == 0 and eng.state.fee_vault == 30


def test_vault_first_then_loss_is_shared_pro_rata():
    # A1 was long (pre_position 5). Eligible: the shorts A2 (weight 1) and A3 (weight 3).
    eng = make({"A1": -110, "A2": 1_000, "A3": 1_000}, {"A2": -1, "A3": -3}, vault=30)
    reps = handle_bankruptcy(eng, "A1", 5)
    assert [(r.kind, r.account, r.qty) for r in reps] == [
        ("INSURANCE_DRAWN", "A1", 30), ("ADL_APPLIED", "A2", 20), ("ADL_APPLIED", "A3", 60),
    ]
    cash = {a: v.free_cash for a, v in eng.state.accounts.items()}
    assert cash["A1"] == 0 and cash["A2"] == 980 and cash["A3"] == 940
    assert eng.state.fee_vault == 0


def test_only_the_other_side_pays_and_liq_never_pays():
    # A3 was short (pre_position -2). Eligible: the longs. A1 is short too and LIQ is long.
    eng = make(
        {"A3": -90, "A1": 500, "A2": 500, "LIQ": 500}, {"A1": -4, "A2": 6, "LIQ": 9}
    )
    reps = handle_bankruptcy(eng, "A3", -2)
    assert [(r.kind, r.account, r.qty) for r in reps] == [("ADL_APPLIED", "A2", 90)]
    assert eng.state.accounts["A1"].free_cash == 500
    assert eng.state.accounts["LIQ"].free_cash == 500


def test_bad_debt_when_nobody_can_share():
    eng = make({"A1": -40, "LIQ": 500}, {"LIQ": -3})
    reps = handle_bankruptcy(eng, "A1", 3)
    assert [(r.kind, r.account, r.qty) for r in reps] == [("BAD_DEBT", "A1", 40)]
    assert eng.state.accounts["A1"].free_cash == -40


def test_price_crash_runs_it_and_price_shock_does_not():
    def crash_engine():
        # A1 holds 5 long with negative cash (it bought on credit); A2 is the 5 short.
        return make({"A1": -400_000_000, "A2": 2_000_000_000}, {"A1": 5, "A2": -5},
                    vault=100_000_000)

    eng = crash_engine()
    reps = eng.process(Event(kind="PRICE_CRASH", mark_price=20_000_000))
    assert [(r.kind, r.account, r.qty) for r in reps] == [
        ("MARK_SET", "", 0),
        ("LIQUIDATED", "A1", 5),
        ("INSURANCE_DRAWN", "A1", 100_000_000),
        ("ADL_APPLIED", "A2", 200_000_000),
    ]
    assert eng.state.accounts["A1"].free_cash == 0

    eng = crash_engine()
    reps = eng.process(Event(kind="PRICE_SHOCK", mark_price=20_000_000))
    assert [r.kind for r in reps] == ["MARK_SET", "LIQUIDATED"]
    assert eng.state.accounts["A1"].free_cash == -300_000_000
