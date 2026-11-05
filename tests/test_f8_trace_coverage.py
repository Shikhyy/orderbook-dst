"""tests/test_f8_trace_coverage.py
The hidden traces of f8_adl_b must reach the hard cases of the bankruptcy rules, not only the
easy ones. A wrapper around the reference procedure records, from the state it receives, which
case each call is, and the totals over the 20 hidden seeds are checked.
"""
import collections

import pytest

import exchange_core.handlers.crash as crash
from exchange_core.config import EngineConfig
from exchange_core.engine import Engine
from graders.hidden_seeds import get_task_seeds
from graders.trace_gen import generate_trace


def _run_seed(seed: int, monkeypatch: pytest.MonkeyPatch) -> collections.Counter:
    stats: collections.Counter = collections.Counter()
    real = crash.handle_bankruptcy

    def spy(engine, account_id, pre_position):
        st = engine.state
        deficit = max(0, -st.accounts[account_id].free_cash)
        if deficit > 0:
            stats["bankruptcies"] += 1
            weights = {
                a: abs(v.position) for a, v in st.accounts.items()
                if a not in ("LIQ", account_id) and v.position != 0
                and (v.position > 0) != (pre_position > 0)
            }
            cover = min(deficit, max(0, st.fee_vault))
            remaining = deficit - cover
            stats["vault_used"] += cover > 0
            stats["vault_covers_all"] += remaining == 0
            if remaining > 0 and not weights:
                stats["bad_debt"] += 1
            if remaining > 0 and weights:
                total = sum(weights.values())
                leftover = remaining - sum(remaining * w // total for w in weights.values())
                stats["loss_sharing"] += 1
                stats["leftover_units"] += leftover > 0
                ranked = sorted(weights, key=lambda a: (-weights[a], a))
                if 0 < leftover < len(ranked):
                    cut_weight = weights[ranked[leftover - 1]]
                    stats["tie_decides_leftover"] += weights[ranked[leftover]] == cut_weight
                numeric = sorted(weights, key=lambda a: int(a[1:]))
                stats["string_order_differs_from_numeric"] += (
                    len(weights) >= 2 and sorted(weights) != numeric
                )
        return real(engine, account_id, pre_position)

    monkeypatch.setattr(crash, "handle_bankruptcy", spy)
    trace = generate_trace(seed, "crash_heavy", 200)
    engine = Engine(EngineConfig(), trace.accounts, trace.mark_price)
    for event in trace.events:
        engine.process(event)
    stats["crash_events"] = trace.trigger_count
    return stats


def test_hidden_traces_reach_every_bankruptcy_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    total: collections.Counter = collections.Counter()
    for seed in get_task_seeds("f8_adl_b", 20):
        per_seed = _run_seed(seed, monkeypatch)
        assert per_seed["crash_events"] >= 10
        assert per_seed["bankruptcies"] >= 2, f"seed {seed} has too few bankruptcies"
        assert per_seed["bad_debt"] + per_seed["loss_sharing"] >= 1
        total.update(per_seed)
    assert total["vault_used"] >= 30
    assert total["loss_sharing"] >= 30
    assert total["bad_debt"] >= 20
    assert total["leftover_units"] >= 20
    assert total["tie_decides_leftover"] >= 5
    assert total["string_order_differs_from_numeric"] >= 10
