# tests/test_worked_examples.py
# Unit tests for each worked example in docs/04_RULEBOOK.md.
# Written before implementation (TDD).

from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.invariants import check_invariants
from exchange_core.types import Event, Report


class TestWorkedExamples:
    """Worked examples from docs/04_RULEBOOK.md."""

    def test_r_g1_margin_rate_worked_example(self):
        """R-G1 Example:
        Order with qty 10, price 100,000,000, rate 2,000 has lock 200,000,000.
        After rate changes to 3,000, this lock stays at 200,000,000.
        A new order with same size gets lock 300,000,000.
        """
        cfg = EngineConfig()
        accounts = {"A1": 1_000_000_000, "LIQ": 10_000_000_000}
        engine = Engine(cfg, accounts, mark_price=100_000_000)

        # Place initial order at rate 2000
        ev1 = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10)
        reps1 = engine.process(ev1)
        assert reps1 == [Report.accepted(1)]
        order1 = engine.state.orders[1]
        assert order1.margin_bps == 2_000
        assert order1.lock == 200_000_000
        assert engine.state.accounts["A1"].locked_margin == 200_000_000

        # Change margin rate to 3000
        ev2 = Event(kind="SET_MARGIN_RATE", bps=3_000)
        reps2 = engine.process(ev2)
        assert reps2 == [Report.margin_rate_set(3_000)]
        assert engine.state.margin_bps == 3_000
        # order1 keeps stored rate and lock
        assert engine.state.orders[1].margin_bps == 2_000
        assert engine.state.orders[1].lock == 200_000_000

        # Place new order with same size, gets lock 300,000,000
        ev3 = Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10)
        reps3 = engine.process(ev3)
        assert reps3 == [Report.accepted(2)]
        order2 = engine.state.orders[2]
        assert order2.margin_bps == 3_000
        assert order2.lock == 300_000_000

        violations = check_invariants(engine.state, 3)
        assert not violations

    def test_r_p4_replace_worked_example(self):
        """R-P4 Example:
        Resting BUY order has qty 10, cum_qty 4, price 100M, rate 2000, lock 120M.
        - REPLACE new_qty 8, same price: keeps priority. Leaves 4. Lock 80M. Release 40M.
        - REPLACE new_qty 4: reject with INVALID_REPLACE.
        - REPLACE new_price 101,000,000, new_qty 10: gets a new prio_seq.
        """
        cfg = EngineConfig()
        accounts = {"A1": 1_000_000_000, "A2": 1_000_000_000, "LIQ": 10_000_000_000}
        engine = Engine(cfg, accounts, mark_price=100_000_000)

        # Place BUY order: qty 10, price 100_000_000
        engine.process(
            Event(kind="NEW_LIMIT", account="A1", side="BUY", price=100_000_000, qty=10)
        )
        # Place SELL order to partially fill 4 units: qty 4, price 100_000_000
        engine.process(
            Event(kind="NEW_LIMIT", account="A2", side="SELL", price=100_000_000, qty=4)
        )

        order = engine.state.orders[1]
        assert order.qty == 10
        assert order.cum_qty == 4
        assert order.leaves == 6
        assert order.lock == 120_000_000
        original_prio = order.prio_seq

        # Case 1: REPLACE new_qty 8, same price
        free_before = engine.state.accounts["A1"].free_cash
        reps_rep1 = engine.process(
            Event(kind="REPLACE", order_id=1, new_price=100_000_000, new_qty=8)
        )
        assert reps_rep1 == [Report.replaced(1)]
        assert order.leaves == 4
        assert order.lock == 80_000_000
        assert order.prio_seq == original_prio
        assert engine.state.accounts["A1"].free_cash == free_before + 40_000_000

        # Case 2: REPLACE new_qty 4 (which is == cum_qty) -> REJECTED(INVALID_REPLACE)
        reps_rep2 = engine.process(
            Event(kind="REPLACE", order_id=1, new_price=100_000_000, new_qty=4)
        )
        assert reps_rep2 == [Report.rejected("INVALID_REPLACE")]
        assert order.qty == 8
        assert order.lock == 80_000_000

        # Case 3: REPLACE new_price 101,000,000, new_qty 10 -> new prio_seq
        reps_rep3 = engine.process(
            Event(kind="REPLACE", order_id=1, new_price=101_000_000, new_qty=10)
        )
        assert reps_rep3 == [Report.replaced(1)]
        assert order.price == 101_000_000
        assert order.qty == 10
        assert order.prio_seq > original_prio

        violations = check_invariants(engine.state, 5)
        assert not violations

    def test_r_f3_fee_worked_example(self):
        """R-F3 Example:
        volume_before = 4,999,980,000, notional = 300,000,000 (3 units at 100,000,000).
        below = 30,000. above = 299,970,000.
        fee below = 82, fee above = 554,944.
        total fee = 555,026.
        rebate = 75,000.
        """
        cfg = EngineConfig()
        accounts = {"MAKER": 10_000_000_000, "TAKER": 10_000_000_000, "LIQ": 10_000_000_000}
        engine = Engine(cfg, accounts, mark_price=100_000_000)

        # Set taker's starting volume
        engine.state.accounts["TAKER"].volume = 4_999_980_000

        # Maker places SELL limit order: qty 3, price 100,000,000
        engine.process(
            Event(kind="NEW_LIMIT", account="MAKER", side="SELL", price=100_000_000, qty=3)
        )

        maker_cash_before = engine.state.accounts["MAKER"].free_cash
        taker_cash_before = engine.state.accounts["TAKER"].free_cash
        vault_before = engine.state.fee_vault

        # Taker buys 3 units at 100,000,000
        reps = engine.process(
            Event(kind="NEW_LIMIT", account="TAKER", side="BUY", price=100_000_000, qty=3)
        )
        assert any(r.kind == "FILL" for r in reps)

        # Check fees
        expected_fee = 555_026
        expected_rebate = 75_000
        notional = 300_000_000

        # Maker receives notional + rebate
        # plus order lock of 60,000,000 released from locked_margin to free_cash
        maker_cash_after = engine.state.accounts["MAKER"].free_cash
        assert maker_cash_after - maker_cash_before == notional + expected_rebate + 60_000_000

        # Taker pays notional + fee
        taker_cash_after = engine.state.accounts["TAKER"].free_cash
        assert taker_cash_before - taker_cash_after == notional + expected_fee

        # Vault change: fee - rebate
        assert engine.state.fee_vault - vault_before == expected_fee - expected_rebate

        # Taker volume updated to volume_before + notional
        assert engine.state.accounts["TAKER"].volume == 4_999_980_000 + notional

        violations = check_invariants(engine.state, 2)
        assert not violations

    def test_r_w5_price_shock_waterfall_case1(self):
        """R-W5 Example Case 1:
        Account A is short 10 units. free_cash = 1,050,000,000. Mark moves to 101,000,000.
        avail = 40,000,000. req = 50,500,000. A in breach.
        Case 1: A has locks of 20,000,000. Stage 1 releases them. avail = 60,000,000 >= req.
        No liquidation.
        """
        cfg = EngineConfig()
        accounts = {"A": 1_070_000_000, "LIQ": 10_000_000_000}
        engine = Engine(cfg, accounts, mark_price=100_000_000)

        # Set up short position of -10
        engine.state.accounts["A"].position = -10

        # Resting order with lock 20,000,000; free_cash = 1,050,000,000
        engine.state.accounts["A"].free_cash = 1_050_000_000
        engine.state.accounts["A"].locked_margin = 20_000_000
        from exchange_core.types import Order
        engine.state.orders[1] = Order(
            order_id=1,
            account="A",
            side="BUY",
            price=100_000_000,
            qty=1,
            cum_qty=0,
            prio_seq=1,
            margin_bps=2_000,
            lock=20_000_000,
            flag="NONE",
        )
        engine.state.initial_total = 1_070_000_000 + 10_000_000_000

        # Shock to 101,000,000
        reps = engine.process(Event(kind="PRICE_SHOCK", mark_price=101_000_000))
        assert Report.mark_set(101_000_000) in reps
        assert Report.cancelled(1, "RISK") in reps
        # No liquidation report
        assert not any(r.kind == "LIQUIDATED" for r in reps)
        # Position unchanged
        assert engine.state.accounts["A"].position == -10
        # Lock released to free cash: 1,050,000,000 + 20,000,000 = 1,070,000,000
        assert engine.state.accounts["A"].free_cash == 1_070_000_000
        assert engine.state.accounts["A"].locked_margin == 0

        violations = check_invariants(engine.state, 1)
        assert not violations

    def test_r_w5_price_shock_waterfall_case2(self):
        """R-W5 Example Case 2:
        Account A is short 10 units. free_cash = 1,050,000,000. Mark moves to 101,000,000.
        Case 2: A has locks of 5,000,000. Stage 1 releases them: avail = 45,000,000 < req.
        Stage 2 liquidates.
        """
        from exchange_core.types import Order
        cfg = EngineConfig()
        accounts = {"A": 1_055_000_000, "LIQ": 10_000_000_000}
        engine = Engine(cfg, accounts, mark_price=100_000_000)

        # Set up short position of -10
        engine.state.accounts["A"].position = -10
        engine.state.accounts["A"].free_cash = 1_050_000_000
        engine.state.accounts["A"].locked_margin = 5_000_000
        engine.state.orders[1] = Order(
            order_id=1,
            account="A",
            side="BUY",
            price=25_000_000,
            qty=1,
            cum_qty=0,
            prio_seq=1,
            margin_bps=2_000,
            lock=5_000_000,
            flag="NONE",
        )
        engine.state.initial_total = 1_055_000_000 + 10_000_000_000

        reps = engine.process(Event(kind="PRICE_SHOCK", mark_price=101_000_000))
        assert Report.mark_set(101_000_000) in reps
        assert Report.cancelled(1, "RISK") in reps
        # Stage 2 liquidates short position (-10): account buys 10 from LIQ
        assert Report.liquidated("A", -10) in reps
        assert engine.state.accounts["A"].position == 0
        assert engine.state.accounts["LIQ"].position == -10
        # Cash transferred at mark_price:
        # After stage 1 cancel: free_cash was 1,050,000,000 + 5,000,000 = 1,055,000,000
        # Paid for 10 units at 101,000,000 = 1,010,000,000
        # Remaining free cash = 1,055,000,000 - 1,010,000,000 = 45,000,000
        assert engine.state.accounts["A"].free_cash == 1_055_000_000 - 1_010_000_000
        assert engine.state.accounts["LIQ"].free_cash == 10_000_000_000 + 1_010_000_000

        violations = check_invariants(engine.state, 1)
        assert not violations
