"""tests/test_report_audit.py
Recompute account positions and cash from reports using a standalone simple
tracker (no import of ledger.py or book.py) and compare with engine state on all profiles.

This test fulfills item A4:
- Independent audit tracking of free_cash, locked_margin, and position
- Recomputed strictly from FILL, CANCELLED, REPLACED, ACCEPTED, and LIQUIDATED reports
- Verified on all trace profiles across multiple seeds
"""
from dataclasses import dataclass

import pytest

from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.intmath import ceil_div, round_half_even
from exchange_core.types import Event, Report
from graders.trace_gen import PROFILES, generate_trace


@dataclass
class TrackedOrder:
    account: str
    price: int
    orig_qty: int
    leaves: int
    bps: int
    lock: int


class IndependentReportAuditTracker:
    """Recomputes free_cash, locked_margin, and position independently.

    Does NOT import or use exchange_core.ledger or exchange_core.book.
    """

    def __init__(
        self,
        initial_accounts: dict[str, int],
        cfg: EngineConfig,
        mark_price: int = 100_000_000,
    ) -> None:
        self.cfg = cfg
        self.free_cash = dict(initial_accounts)
        self.locked_margin = {k: 0 for k in initial_accounts}
        self.positions = {k: 0 for k in initial_accounts}
        self.volumes = {k: 0 for k in initial_accounts}
        self.current_bps = cfg.margin_bps_default
        self.current_mark = mark_price
        self.orders: dict[int, TrackedOrder] = {}

    def on_event_reports(self, event: Event, reports: list[Report]) -> None:
        if event.kind == "FIX_MSG" and event.body:
            account = event.body.account
            price = event.body.price
            qty = event.body.qty
            new_price = event.body.new_price
            new_qty = event.body.new_qty
        else:
            account = event.account
            price = event.price
            qty = event.qty
            new_price = event.new_price
            new_qty = event.new_qty

        leg_idx = 0
        for r in reports:
            if r.kind == "MARK_SET":
                self.current_mark = r.mark_price
            elif r.kind == "MARGIN_RATE_SET":
                self.current_bps = r.bps
            elif r.kind == "FUNDING_APPLIED":
                # Independent re-derivation of R-Y1 to R-Y2 from the tracker's own positions.
                assert r.bps == max(-3000, min(3000, event.bps))
                for acc_id in sorted(self.positions):
                    pos = self.positions[acc_id]
                    if pos == 0 or r.bps == 0:
                        continue
                    amount = round_half_even(abs(pos) * self.current_mark * abs(r.bps), 1_000_000)
                    pays = (pos > 0) == (r.bps > 0)
                    self.free_cash[acc_id] += -amount if pays else amount
            elif r.kind == "ACCEPTED":
                if event.kind == "BASKET":
                    leg = event.legs[leg_idx]
                    l_price = leg.price
                    l_qty = leg.qty
                    leg_idx += 1
                else:
                    l_price = price
                    l_qty = qty
                lock = ceil_div(l_qty * l_price * self.current_bps, 10000)
                self.free_cash[account] -= lock
                self.locked_margin[account] += lock
                self.orders[r.order_id] = TrackedOrder(
                    account=account,
                    price=l_price,
                    orig_qty=l_qty,
                    leaves=l_qty,
                    bps=self.current_bps,
                    lock=lock,
                )
            elif r.kind == "FILL":
                buyer = self.orders[r.buy_order_id].account
                seller = self.orders[r.sell_order_id].account
                notional = r.qty * r.price
                self.free_cash[buyer] -= notional
                self.free_cash[seller] += notional
                self.positions[buyer] += r.qty
                self.positions[seller] -= r.qty

                for oid in (r.buy_order_id, r.sell_order_id):
                    o = self.orders[oid]
                    o.leaves -= r.qty
                    new_lock = ceil_div(o.leaves * o.price * o.bps, 10000)
                    delta = o.lock - new_lock
                    o.lock = new_lock
                    self.locked_margin[o.account] -= delta
                    self.free_cash[o.account] += delta

                taker_acc = self.orders[r.taker_order_id].account
                maker_acc = seller if taker_acc == buyer else buyer

                vol_before = self.volumes[taker_acc]
                self.volumes[taker_acc] += notional
                self.volumes[maker_acc] += notional

                if vol_before + notional <= self.cfg.tier_threshold:
                    fee = round_half_even(notional * self.cfg.taker_ppm_t0, self.cfg.ppm)
                elif vol_before >= self.cfg.tier_threshold:
                    fee = round_half_even(notional * self.cfg.taker_ppm_t1, self.cfg.ppm)
                else:
                    below = self.cfg.tier_threshold - vol_before
                    above = notional - below
                    fee = round_half_even(
                        below * self.cfg.taker_ppm_t0, self.cfg.ppm
                    ) + round_half_even(above * self.cfg.taker_ppm_t1, self.cfg.ppm)

                rebate = round_half_even(notional * self.cfg.maker_rebate_ppm, self.cfg.ppm)
                self.free_cash[taker_acc] -= fee
                self.free_cash[maker_acc] += rebate

            elif r.kind == "CANCELLED":
                if r.order_id in self.orders:
                    o = self.orders[r.order_id]
                    self.locked_margin[o.account] -= o.lock
                    self.free_cash[o.account] += o.lock
                    o.lock = 0
                    o.leaves = 0

            elif r.kind == "REPLACED":
                o = self.orders[r.order_id]
                cum_qty = o.orig_qty - o.leaves
                new_leaves = new_qty - cum_qty
                new_lock = ceil_div(new_leaves * new_price * o.bps, 10000)
                delta = new_lock - o.lock
                self.free_cash[o.account] -= delta
                self.locked_margin[o.account] += delta
                o.price = new_price
                o.orig_qty = new_qty
                o.leaves = new_leaves
                o.lock = new_lock

            elif r.kind == "LIQUIDATED":
                acc = r.account
                qty = r.qty
                if qty > 0:
                    transfer = qty * self.current_mark
                    self.free_cash[acc] += transfer
                    self.free_cash["LIQ"] -= transfer
                    self.positions[acc] = 0
                    self.positions["LIQ"] += qty
                else:
                    transfer = abs(qty) * self.current_mark
                    self.free_cash[acc] -= transfer
                    self.free_cash["LIQ"] += transfer
                    self.positions[acc] = 0
                    self.positions["LIQ"] += qty


AUDIT_SEEDS = [1, 2, 3, 4, 5, 100, 200, 300, 400, 500]


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("seed", AUDIT_SEEDS)
def test_report_audit_state_reconstruction(profile: str, seed: int) -> None:
    """Verify that positions and cash independently recomputed from reports match engine state."""
    cfg = EngineConfig()
    accounts = {
        "A1": 500_000_000,
        "A2": 500_000_000,
        "A3": 500_000_000,
        "LIQ": 10_000_000_000,
    }
    clean_fix = profile == "fix_noisy"
    trace = generate_trace(
        seed=seed,
        profile=profile,
        num_events=100,
        clean_fix=clean_fix,
    )
    engine = Engine(cfg, accounts, 100_000_000)
    tracker = IndependentReportAuditTracker(accounts, cfg, 100_000_000)

    for event in trace.events:
        reports = engine.process(event)
        tracker.on_event_reports(event, reports)

    for aid in accounts:
        eng_acc = engine.state.accounts[aid]
        assert tracker.positions[aid] == eng_acc.position, (
            f"Position mismatch on {profile} seed {seed} for {aid}: "
            f"tracker={tracker.positions[aid]} != engine={eng_acc.position}"
        )
        assert tracker.free_cash[aid] == eng_acc.free_cash, (
            f"Free cash mismatch on {profile} seed {seed} for {aid}: "
            f"tracker={tracker.free_cash[aid]} != engine={eng_acc.free_cash}"
        )
        assert tracker.locked_margin[aid] == eng_acc.locked_margin, (
            f"Locked margin mismatch on {profile} seed {seed} for {aid}: "
            f"tracker={tracker.locked_margin[aid]} != engine={eng_acc.locked_margin}"
        )
