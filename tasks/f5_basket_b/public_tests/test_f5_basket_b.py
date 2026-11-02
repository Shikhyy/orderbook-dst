"""tasks/f5_basket_b/public_tests/test_f5_basket_b.py
Public unit tests for task f5_basket_b.
"""
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.types import BasketLeg, Event, Report


def test_all_legs_succeed():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    leg0 = BasketLeg(side="BUY", price=90_000_000, qty=2, flag="POST_ONLY")
    leg1 = BasketLeg(side="BUY", price=85_000_000, qty=2, flag="POST_ONLY")
    reps = eng.process(Event(kind="BASKET", account="A1", legs=(leg0, leg1)))
    assert len(reps) == 3
    assert reps[0] == Report.accepted(1)
    assert reps[1] == Report.accepted(2)
    assert reps[2] == Report.basket_committed()


def test_leg_1_fails():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # Leg 0 has invalid price (not tick aligned)
    leg0 = BasketLeg(side="BUY", price=90_000_005, qty=2, flag="POST_ONLY")
    reps = eng.process(Event(kind="BASKET", account="A1", legs=(leg0,)))
    assert reps == [Report.basket_rolled_back(0)]


def test_post_only_fails_after_earlier_fills():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # Resting sell order @ 100M
    eng.process(Event(kind="NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=5))
    h_before = eng.state_hash()

    # Leg 0 fills 2 units @ 100M, leg 1 is POST_ONLY @ 100M which would cross
    leg0 = BasketLeg(side="BUY", price=100_000_000, qty=2, flag="IOC")
    leg1 = BasketLeg(side="BUY", price=100_000_000, qty=2, flag="POST_ONLY")

    reps = eng.process(Event(kind="BASKET", account="A1", legs=(leg0, leg1)))
    assert reps == [Report.basket_rolled_back(1)]
    assert eng.state_hash() == h_before


def test_reject_by_margin():
    cfg = EngineConfig()
    accounts = {"A1": 50_000_000, "LIQ": 10_000_000_000}  # 50M cash
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # Leg 0 needs 20M margin, leg 1 needs 40M margin (total 60M > 50M)
    leg0 = BasketLeg(side="BUY", price=100_000_000, qty=1, flag="POST_ONLY")
    leg1 = BasketLeg(side="BUY", price=100_000_000, qty=2, flag="POST_ONLY")
    reps = eng.process(Event(kind="BASKET", account="A1", legs=(leg0, leg1)))
    assert reps == [Report.basket_rolled_back(1)]


def test_empty_basket():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    reps = eng.process(Event(kind="BASKET", account="A1", legs=()))
    assert reps == [Report.basket_committed()]


def test_reports_on_commit():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    leg0 = BasketLeg(side="BUY", price=90_000_000, qty=1, flag="POST_ONLY")
    leg1 = BasketLeg(side="BUY", price=89_000_000, qty=1, flag="POST_ONLY")
    reps = eng.process(Event(kind="BASKET", account="A1", legs=(leg0, leg1)))
    assert len(reps) == 3
    assert reps[0].kind == "ACCEPTED"
    assert reps[1].kind == "ACCEPTED"
    assert reps[2].kind == "BASKET_COMMITTED"


def test_reports_on_rollback():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # Leg 0 succeeds, leg 1 fails
    leg0 = BasketLeg(side="BUY", price=90_000_000, qty=1, flag="POST_ONLY")
    leg1 = BasketLeg(side="BUY", price=90_000_005, qty=1, flag="POST_ONLY")
    reps = eng.process(Event(kind="BASKET", account="A1", legs=(leg0, leg1)))
    # Only 1 report, no ACCEPTED report for leg 0
    assert reps == [Report.basket_rolled_back(1)]


def test_book_restored_on_rollback():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    assert len(eng.state.orders) == 0
    leg0 = BasketLeg(side="BUY", price=90_000_000, qty=1, flag="POST_ONLY")
    leg1 = BasketLeg(side="BUY", price=-10, qty=1, flag="POST_ONLY")
    eng.process(Event(kind="BASKET", account="A1", legs=(leg0, leg1)))
    assert len(eng.state.orders) == 0


def test_accounts_restored_on_rollback():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # Resting sell
    eng.process(Event(kind="NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=5))
    h_before = eng.state_hash()
    leg0 = BasketLeg(side="BUY", price=100_000_000, qty=2, flag="IOC")  # would fill
    leg1 = BasketLeg(side="BUY", price=100_000_000, qty=2, flag="POST_ONLY")  # fails
    eng.process(Event(kind="BASKET", account="A1", legs=(leg0, leg1)))
    assert eng.state_hash() == h_before
    assert eng.state.accounts["A1"].free_cash == 1_000_000_000
    assert eng.state.accounts["A1"].volume == 0
    assert eng.state.fee_vault == 0
