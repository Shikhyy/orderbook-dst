"""tasks/f1_fee_b/public_tests/test_f1_fee_b.py
Public tests for task f1_fee_b.
"""
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.handlers.settle import settle_fill
from exchange_core.types import Fill, Report


def _make_engine():
    cfg = EngineConfig()
    accounts = {"A1": 100_000_000_000, "A2": 100_000_000_000}
    return Engine(cfg, accounts, 100_000_000)


def test_cash_transfer():
    eng = _make_engine()
    fill = Fill(
        buy_order_id=1,
        sell_order_id=2,
        price=100_000_000,
        qty=10,
        taker_order_id=1,
        buyer="A1",
        seller="A2",
    )
    # notional = 1_000_000_000; fee = 2_750_000 (A1); rebate = 250_000 (A2)
    settle_fill(eng, fill)
    assert eng.state.accounts["A1"].free_cash == 100_000_000_000 - 1_000_000_000 - 2_750_000
    assert eng.state.accounts["A2"].free_cash == 100_000_000_000 + 1_000_000_000 + 250_000


def test_position_update():
    eng = _make_engine()
    fill = Fill(
        buy_order_id=1,
        sell_order_id=2,
        price=100_000_000,
        qty=10,
        taker_order_id=1,
        buyer="A1",
        seller="A2",
    )
    settle_fill(eng, fill)
    assert eng.state.accounts["A1"].position == 10
    assert eng.state.accounts["A2"].position == -10


def test_fee_below_threshold():
    eng = _make_engine()
    fill = Fill(
        buy_order_id=1,
        sell_order_id=2,
        price=100_000_000,
        qty=20,
        taker_order_id=1,
        buyer="A1",
        seller="A2",
    )
    # notional = 2B, fee = 5_500_000
    settle_fill(eng, fill)
    assert eng.state.accounts["A1"].free_cash == 100_000_000_000 - 2_000_000_000 - 5_500_000


def test_rebate():
    eng = _make_engine()
    fill = Fill(
        buy_order_id=1,
        sell_order_id=2,
        price=100_000_000,
        qty=20,
        taker_order_id=1,
        buyer="A1",
        seller="A2",
    )
    settle_fill(eng, fill)
    # rebate = 2B * 250 ppm = 500_000
    assert eng.state.accounts["A2"].free_cash == 100_000_000_000 + 2_000_000_000 + 500_000


def test_vault_update():
    eng = _make_engine()
    fill = Fill(
        buy_order_id=1,
        sell_order_id=2,
        price=100_000_000,
        qty=20,
        taker_order_id=1,
        buyer="A1",
        seller="A2",
    )
    settle_fill(eng, fill)
    # vault += fee - rebate = 5_500_000 - 500_000 = 5_000_000
    assert eng.state.fee_vault == 5_000_000


def test_volume_update():
    eng = _make_engine()
    fill = Fill(
        buy_order_id=1,
        sell_order_id=2,
        price=100_000_000,
        qty=15,
        taker_order_id=1,
        buyer="A1",
        seller="A2",
    )
    settle_fill(eng, fill)
    assert eng.state.accounts["A1"].volume == 1_500_000_000
    assert eng.state.accounts["A2"].volume == 1_500_000_000


def test_crossing_fill():
    eng = _make_engine()
    eng.state.accounts["A1"].volume = 4_000_010_000
    fill = Fill(
        buy_order_id=1,
        sell_order_id=2,
        price=100_000_000,
        qty=20,
        taker_order_id=1,
        buyer="A1",
        seller="A2",
    )
    # notional = 2B; below = 1B @ 2750 ppm = 2_750_000; above = 1B @ 1850 ppm = 1_850_000
    # fee = 4_600_000
    settle_fill(eng, fill)
    assert eng.state.accounts["A1"].free_cash == 100_000_000_000 - 2_000_000_000 - 4_600_000


def test_two_fills_in_a_row():
    eng = _make_engine()
    fill1 = Fill(
        buy_order_id=1,
        sell_order_id=2,
        price=100_000_000,
        qty=30,
        taker_order_id=1,
        buyer="A1",
        seller="A2",
    )
    settle_fill(eng, fill1)
    assert eng.state.accounts["A1"].volume == 3_000_000_000

    fill2 = Fill(
        buy_order_id=3,
        sell_order_id=4,
        price=100_000_000,
        qty=30,
        taker_order_id=3,
        buyer="A1",
        seller="A2",
    )
    settle_fill(eng, fill2)
    assert eng.state.accounts["A1"].volume == 6_000_000_000


def test_fee_and_volume_order():
    eng = _make_engine()
    eng.state.accounts["A1"].volume = 4_000_010_000
    fill = Fill(
        buy_order_id=1,
        sell_order_id=2,
        price=100_000_000,
        qty=20,
        taker_order_id=1,
        buyer="A1",
        seller="A2",
    )
    reps = settle_fill(eng, fill)
    assert reps == [Report.fill(1, 2, 100_000_000, 20, 1)]
    assert eng.state.accounts["A1"].free_cash == 100_000_000_000 - 2_000_000_000 - 4_600_000
    assert eng.state.accounts["A1"].volume == 4_000_010_000 + 2_000_000_000
