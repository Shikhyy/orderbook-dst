# tests/test_rules_pure.py
# Unit tests for pure rules in exchange_core/rules/ (Variant A targets).
# Tests every branch and edge case.

from exchange_core.config import EngineConfig
from exchange_core.rules.fee_rule import compute_maker_rebate, compute_taker_fee
from exchange_core.rules.replace_rule import decide_replace
from exchange_core.rules.session_rule import on_message
from exchange_core.rules.waterfall_rule import plan_waterfall
from exchange_core.state import SessionState
from exchange_core.types import AccountView, Event, Order


class TestFeeRulePure:
    """Rules R-F2 and R-F3."""

    def test_fee_above_threshold(self):
        cfg = EngineConfig()
        # Already at or above threshold
        fee = compute_taker_fee(cfg.tier_threshold + 1_000, 100_000_000, cfg)
        expected = round(100_000_000 * 1850 / 1_000_000)
        assert fee == expected

    def test_fee_exactly_on_threshold(self):
        cfg = EngineConfig()
        # volume_before + notional == threshold (inclusive <= boundary)
        fee = compute_taker_fee(cfg.tier_threshold - 100_000_000, 100_000_000, cfg)
        expected = round(100_000_000 * 2750 / 1_000_000)
        assert fee == expected

    def test_fee_crossing_split(self):
        cfg = EngineConfig()
        vol_before = 4_999_980_000
        notional = 300_000_000
        fee = compute_taker_fee(vol_before, notional, cfg)
        assert fee == 555_026

    def test_maker_rebate(self):
        cfg = EngineConfig()
        assert compute_maker_rebate(300_000_000, cfg) == 75_000


class TestReplaceRulePure:
    """Rules R-P1, R-P2, R-P3."""

    def _sample_order(self) -> Order:
        return Order(
            order_id=1, account="A1", side="BUY", price=100_000_000,
            qty=10, cum_qty=4, prio_seq=1, margin_bps=2_000, lock=120_000_000, flag="NONE"
        )

    def test_invalid_price_zero_or_negative(self):
        cfg = EngineConfig()
        order = self._sample_order()
        d1 = decide_replace(order, 0, 10, cfg)
        assert not d1.ok and d1.reason == "INVALID_ORDER"
        d2 = decide_replace(order, -100_000, 10, cfg)
        assert not d2.ok and d2.reason == "INVALID_ORDER"

    def test_invalid_price_not_tick_multiple(self):
        cfg = EngineConfig()
        order = self._sample_order()
        d = decide_replace(order, 100_005, 10, cfg)
        assert not d.ok and d.reason == "INVALID_ORDER"

    def test_qty_equal_or_below_cum_qty(self):
        cfg = EngineConfig()
        order = self._sample_order()  # cum_qty = 4
        d_equal = decide_replace(order, 100_000_000, 4, cfg)
        assert not d_equal.ok and d_equal.reason == "INVALID_REPLACE"
        d_below = decide_replace(order, 100_000_000, 3, cfg)
        assert not d_below.ok and d_below.reason == "INVALID_REPLACE"

    def test_decrease_keeps_priority(self):
        cfg = EngineConfig()
        order = self._sample_order()  # qty = 10, price = 100M
        d = decide_replace(order, 100_000_000, 8, cfg)
        assert d.ok and d.keep_priority and d.new_leaves == 4

    def test_same_qty_and_price_keeps_priority(self):
        cfg = EngineConfig()
        order = self._sample_order()
        d = decide_replace(order, 100_000_000, 10, cfg)
        assert d.ok and d.keep_priority and d.new_leaves == 6

    def test_increase_loses_priority(self):
        cfg = EngineConfig()
        order = self._sample_order()
        d = decide_replace(order, 100_000_000, 12, cfg)
        assert d.ok and not d.keep_priority and d.new_leaves == 8

    def test_price_change_loses_priority(self):
        cfg = EngineConfig()
        order = self._sample_order()
        d = decide_replace(order, 101_000_000, 8, cfg)
        assert d.ok and not d.keep_priority and d.new_leaves == 4


class TestSessionRulePure:
    """Rules R-S1 to R-S7."""

    def test_epoch_mismatch(self):
        session = SessionState(epoch=0, next_seq=1, buffer={})
        msg = Event(kind="FIX_MSG", session="S1", epoch=1, seq=1, poss_dup=False, body=None)
        outcome = on_message(session, msg)
        assert len(outcome.reports) == 1
        assert outcome.reports[0].kind == "DISCARDED" and outcome.reports[0].reason == "EPOCH"

    def test_seq_too_low_duplicate(self):
        session = SessionState(epoch=0, next_seq=5, buffer={})
        msg = Event(kind="FIX_MSG", session="S1", epoch=0, seq=3, poss_dup=True, body=None)
        outcome = on_message(session, msg)
        assert outcome.reports[0].kind == "DISCARDED" and outcome.reports[0].reason == "DUPLICATE"

    def test_seq_too_low_not_dup(self):
        session = SessionState(epoch=0, next_seq=5, buffer={})
        msg = Event(kind="FIX_MSG", session="S1", epoch=0, seq=3, poss_dup=False, body=None)
        outcome = on_message(session, msg)
        assert outcome.reports[0].kind == "DISCARDED" and outcome.reports[0].reason == "SEQ_TOO_LOW"

    def test_gap_and_drain(self):
        session = SessionState(epoch=0, next_seq=1, buffer={})
        msg3 = Event(kind="FIX_MSG", session="S1", epoch=0, seq=3, poss_dup=False, body="body3")
        msg2 = Event(kind="FIX_MSG", session="S1", epoch=0, seq=2, poss_dup=False, body="body2")
        msg1 = Event(kind="FIX_MSG", session="S1", epoch=0, seq=1, poss_dup=False, body="body1")

        # Send 3 first: buffered
        out3 = on_message(session, msg3)
        assert out3.reports[0].kind == "BUFFERED"
        assert session.next_seq == 1

        # Send duplicate 3: discarded as duplicate buffered
        out3_dup = on_message(session, msg3)
        assert out3_dup.reports[0].kind == "DISCARDED"
        assert out3_dup.reports[0].reason == "DUPLICATE_BUFFERED"

        # Send 2: buffered
        out2 = on_message(session, msg2)
        assert out2.reports[0].kind == "BUFFERED"

        # Send 1: in order, drains 2 and 3!
        out1 = on_message(session, msg1)
        assert len(out1.to_process) == 3
        assert [m.seq for m in out1.to_process] == [1, 2, 3]
        assert session.next_seq == 4
        assert len(session.buffer) == 0


class TestWaterfallRulePure:
    """Rules R-W2, R-W4."""

    def test_zero_position_never_in_breach(self):
        cfg = EngineConfig()
        view = AccountView(account_id="A1", free_cash=-1000, locked_margin=0, position=0)
        plan = plan_waterfall(view, mark=100_000_000, cfg=cfg)
        assert not plan.in_breach_stage1

    def test_avail_above_req_no_breach(self):
        cfg = EngineConfig()
        view = AccountView(account_id="A1", free_cash=100_000_000, locked_margin=0, position=1)
        plan = plan_waterfall(view, mark=100_000_000, cfg=cfg)
        assert not plan.in_breach_stage1

    def test_breach_resolved_by_stage1(self):
        cfg = EngineConfig()
        # free_cash = 1,050M, mark = 101M, pos = -10 -> avail = 40M < 50.5M req
        # locked = 20M -> stage 2 avail = 1,070M - 1,010M = 60M >= 50.5M
        view = AccountView(
            account_id="A",
            free_cash=1_050_000_000,
            locked_margin=20_000_000,
            position=-10,
        )
        plan = plan_waterfall(view, mark=101_000_000, cfg=cfg)
        assert plan.in_breach_stage1
        assert not plan.in_breach_stage2
        assert plan.liquidate_qty == 0

    def test_breach_requires_liquidation(self):
        cfg = EngineConfig()
        # free_cash = 1,050M, mark = 101M, pos = -10 -> avail = 40M < 50.5M req
        # locked = 5M -> stage 2 avail = 1,055M - 1,010M = 45M < 50.5M
        view = AccountView(
            account_id="A",
            free_cash=1_050_000_000,
            locked_margin=5_000_000,
            position=-10,
        )
        plan = plan_waterfall(view, mark=101_000_000, cfg=cfg)
        assert plan.in_breach_stage1
        assert plan.in_breach_stage2
        assert plan.liquidate_qty == -10
