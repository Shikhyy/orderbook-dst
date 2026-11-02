"""tests/test_differential.py
Differential (N-version) testing between primary reference and reference_alt implementations.
See docs/09_TEST_PLAN.md section 4.
"""
from typing import Any

import pytest

from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from exchange_core.types import Event, Report
from graders.trace_gen import PROFILES, generate_trace


def run_engine_trace(
    engine_cls: Any,
    events: list[Event],
    accounts: dict[str, int],
    cfg: EngineConfig,
    mark_price: int = 100_000_000,
) -> tuple[list[list[Report]], str]:
    """Run an engine over an event trace and return all emitted reports and final state hash."""
    engine = engine_cls(cfg, accounts, mark_price=mark_price)
    all_reports: list[list[Report]] = []
    for event in events:
        reports = engine.process(event)
        all_reports.append(reports)
    return all_reports, engine.state_hash()


def make_alt_engine_class() -> Any:
    """Build an Engine class wired to use reference_alt handlers and rules."""
    import reference_alt.handlers.basket as alt_basket
    import reference_alt.handlers.cancel as alt_cancel
    import reference_alt.handlers.fix as alt_fix
    import reference_alt.handlers.margin_rate as alt_margin_rate
    import reference_alt.handlers.new_limit as alt_new_limit
    import reference_alt.handlers.replace as alt_replace
    import reference_alt.handlers.shock as alt_shock

    class AltEngine(Engine):
        def dispatch(self, event: Event) -> list[Report]:
            handlers = {
                "NEW_LIMIT": alt_new_limit.handle_new_limit,
                "CANCEL": alt_cancel.handle_cancel,
                "REPLACE": alt_replace.handle_replace,
                "SET_MARGIN_RATE": alt_margin_rate.handle_margin_rate,
                "PRICE_SHOCK": alt_shock.handle_shock,
                "FIX_MSG": alt_fix.handle_fix,
                "SESSION_RESET": alt_fix.handle_fix,
                "BASKET": alt_basket.handle_basket,
            }
            handler = handlers.get(event.kind)
            if handler:
                return handler(self, event)
            return [Report.rejected(f"UNKNOWN_EVENT_{event.kind}")]

    return AltEngine


@pytest.fixture(scope="module")
def alt_engine_cls() -> Any:
    return make_alt_engine_class()


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("seed_offset", [0, 1, 2, 3, 4])
def test_differential_equivalence(alt_engine_cls: Any, profile: str, seed_offset: int) -> None:
    """Verify that reference and reference_alt produce identical reports and state hashes."""
    cfg = EngineConfig()
    base_seed = 1000 + seed_offset * 100
    clean = (profile == "fix_noisy")
    trace_res = generate_trace(seed=base_seed, profile=profile, num_events=60, clean_fix=clean)
    events = trace_res.events

    accounts = {
        "A1": 500_000_000,
        "A2": 500_000_000,
        "A3": 500_000_000,
        "LIQ": 10_000_000_000,
    }

    ref_reports, ref_hash = run_engine_trace(Engine, events, accounts, cfg)
    alt_reports, alt_hash = run_engine_trace(alt_engine_cls, events, accounts, cfg)

    msg_len = f"Report length mismatch on profile={profile}, seed={base_seed}"
    assert len(ref_reports) == len(alt_reports), msg_len

    for i, (r_ref, r_alt) in enumerate(zip(ref_reports, alt_reports)):
        msg_ev = (
            f"Report mismatch at event {i} ({events[i].kind}) on "
            f"profile={profile}, seed={base_seed}: {r_ref} != {r_alt}"
        )
        assert r_ref == r_alt, msg_ev

    msg_hash = (
        f"State hash mismatch on profile={profile}, seed={base_seed}: "
        f"{ref_hash} != {alt_hash}"
    )
    assert ref_hash == alt_hash, msg_hash
