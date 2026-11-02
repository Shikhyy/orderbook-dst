"""tasks/f4_waterfall_b/public_tests/test_f4_waterfall_b.py
Public unit tests for task f4_waterfall_b.
"""
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.types import Event, Report


def test_no_breach():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # A1 has 0 position
    reps = eng.process(Event(kind="PRICE_SHOCK", mark_price=105_000_000))
    assert reps == [Report.mark_set(105_000_000)]
    assert eng.state.mark_price == 105_000_000


def test_breach_resolved_by_stage1():
    cfg = EngineConfig()
    # A1 has 500M cash. Short 5 units at 100M -> received 500M cash -> cash = 1000M. Pos = -5.
    accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # Build positions: A1 SELL 5 to A2 BUY 5
    eng.process(Event(kind="NEW_LIMIT", account="A2", side="BUY", price=100_000_000, qty=5))
    eng.process(Event(kind="NEW_LIMIT", account="A1", side="SELL", price=100_000_000, qty=5))
    # A1 places resting BUY order locking margin: 1 unit @ 90M (lock = 18M)
    eng.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=90_000_000, qty=1))
    o_id = eng.state.next_order_id - 1

    # Price shocks up to 190M.
    # A1 pos = -5. req = ceil(5 * 190M * 500 / 10000) = 47.5M.
    # avail before cancel: free_cash + (-5 * 190M).
    # Setting price so avail < req before cancel, but avail >= req after cancel releases 18M lock.
    eng.state.accounts["A1"].free_cash = 935_000_000  # avail = 935M - 950M = -15M < 47.5M (breach!)
    # After releasing 18M: free_cash = 953M. avail = 953M - 950M = 3M... let us set exact numbers:
    # We want: free_cash_before + (-5 * 190M) < 47.5M
    # and: free_cash_before + 18M + (-5 * 190M) >= 47.5M
    # -> free_cash_before - 950M < 47.5M  => free_cash_before < 997.5M
    # -> free_cash_before + 18M - 950M >= 47.5M => free_cash_before >= 979.5M
    eng.state.accounts["A1"].free_cash = 980_000_000

    reps = eng.process(Event(kind="PRICE_SHOCK", mark_price=190_000_000))
    # Must cancel order o_id, but NOT liquidate
    assert Report.mark_set(190_000_000) in reps
    assert Report.cancelled(o_id, "RISK") in reps
    assert not any(r.kind == "LIQUIDATED" for r in reps)
    assert eng.state.accounts["A1"].position == -5
    assert eng.state.accounts["A1"].locked_margin == 0


def test_breach_needs_stage2():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # A1 short 5 units
    eng.process(Event(kind="NEW_LIMIT", account="A2", side="BUY", price=100_000_000, qty=5))
    eng.process(Event(kind="NEW_LIMIT", account="A1", side="SELL", price=100_000_000, qty=5))
    # Severe shock up to 300M
    reps = eng.process(Event(kind="PRICE_SHOCK", mark_price=300_000_000))
    assert Report.mark_set(300_000_000) in reps
    assert Report.liquidated("A1", -5) in reps
    assert eng.state.accounts["A1"].position == 0
    assert eng.state.accounts["LIQ"].position == -5


def test_long_position_liquidated():
    cfg = EngineConfig()
    accounts = {"A1": 200_000_000, "A2": 2_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # A1 buys 10 @ 100M
    eng.process(Event(kind="NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=10))
    eng.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10))
    # A1 cash went down by 1000M. Let free_cash = 10_000_000, pos = 10.
    # Price crashes to 10_000_000.
    # avail = 10M + 10 * 10M = 110M. req = ceil(10 * 10M * 500 / 10000) = 5M.
    # Let crash to 1_000_000: avail = -790M + 10M = negative.
    liq_cash_before = eng.state.accounts["LIQ"].free_cash
    reps = eng.process(Event(kind="PRICE_SHOCK", mark_price=10_000_000))
    # Long liquidated: sells 10 to LIQ at 10M = 100M cash transfer from LIQ to A1
    assert Report.liquidated("A1", 10) in reps
    assert eng.state.accounts["A1"].position == 0
    assert eng.state.accounts["LIQ"].position == 10
    assert eng.state.accounts["LIQ"].free_cash == liq_cash_before - 100_000_000


def test_short_position_liquidated():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # A1 sells 5 @ 100M to A2
    eng.process(Event(kind="NEW_LIMIT", account="A2", side="BUY", price=100_000_000, qty=5))
    eng.process(Event(kind="NEW_LIMIT", account="A1", side="SELL", price=100_000_000, qty=5))
    liq_cash_before = eng.state.accounts["LIQ"].free_cash
    reps = eng.process(Event(kind="PRICE_SHOCK", mark_price=400_000_000))
    # Short liquidated: buys 5 from LIQ at 400M = 2000M cash transfer from A1 to LIQ
    assert Report.liquidated("A1", -5) in reps
    assert eng.state.accounts["A1"].position == 0
    assert eng.state.accounts["LIQ"].position == -5
    assert eng.state.accounts["LIQ"].free_cash == liq_cash_before + 2_000_000_000


def test_multiple_accounts_in_order():
    cfg = EngineConfig()
    accounts = {"B2": 1_000_000_000, "A1": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # Both B2 and A1 take short positions
    eng.process(Event(kind="NEW_LIMIT", account="LIQ", side="BUY", price=100_000_000, qty=10))
    eng.process(Event(kind="NEW_LIMIT", account="A1", side="SELL", price=100_000_000, qty=5))
    eng.process(Event(kind="NEW_LIMIT", account="B2", side="SELL", price=100_000_000, qty=5))
    reps = eng.process(Event(kind="PRICE_SHOCK", mark_price=400_000_000))
    # Reports must have A1 liquidated before B2
    liq_reps = [r for r in reps if r.kind == "LIQUIDATED"]
    assert len(liq_reps) == 2
    assert liq_reps[0].account == "A1"
    assert liq_reps[1].account == "B2"


def test_zero_position_no_breach():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # A1 places resting order
    eng.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=90_000_000, qty=2))
    reps = eng.process(Event(kind="PRICE_SHOCK", mark_price=10_000_000))
    assert reps == [Report.mark_set(10_000_000)]
    assert len(eng.state.orders) == 1  # Order not cancelled


def test_liq_account_excluded():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "LIQ": 100_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    # Even if LIQ has small balance or negative equity, LIQ is never liquidated
    reps = eng.process(Event(kind="PRICE_SHOCK", mark_price=200_000_000))
    assert not any(r.account == "LIQ" for r in reps)


def test_report_order():
    cfg = EngineConfig()
    accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
    eng = Engine(cfg, accounts, mark_price=100_000_000)
    eng.process(Event(kind="NEW_LIMIT", account="A2", side="BUY", price=100_000_000, qty=5))
    eng.process(Event(kind="NEW_LIMIT", account="A1", side="SELL", price=100_000_000, qty=5))
    eng.process(Event(kind="NEW_LIMIT", account="A1", side="BUY", price=90_000_000, qty=1))
    reps = eng.process(Event(kind="PRICE_SHOCK", mark_price=400_000_000))
    kinds = [r.kind for r in reps]
    assert kinds[0] == "MARK_SET"
    assert kinds[1] == "CANCELLED"
    assert kinds[2] == "LIQUIDATED"
