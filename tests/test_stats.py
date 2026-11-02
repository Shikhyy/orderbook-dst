"""tests/test_stats.py
Unit tests for statistics, pass@k, pass^k, bootstrap, and McNemar test.
Values verified against hand-calculated results.
See docs/11_PROMPT_PACK.md section 7 and docs/08_HARNESS_AND_STATS.md section 9.
"""
from pathlib import Path

import pytest

from harness.report import generate_report
from harness.stats import (
    bootstrap_ci,
    compute_mttif,
    compute_pass_at_k,
    compute_pass_pow_k,
    mcnemar_exact_pvalue,
    paired_comparison_a_vs_b,
)


def test_pass_at_k_hand_calculated():
    # n=5, c=2, k=1 -> 1 - C(3,1)/C(5,1) = 1 - 3/5 = 0.40
    assert pytest.approx(compute_pass_at_k(5, 2, 1), rel=1e-6) == 0.40

    # n=5, c=2, k=2 -> 1 - C(3,2)/C(5,2) = 1 - 3/10 = 0.70
    assert pytest.approx(compute_pass_at_k(5, 2, 2), rel=1e-6) == 0.70

    # n=5, c=2, k=5 -> n-c = 3 < 5 -> any subset of 5 has at least 2 passes = 1.0
    assert compute_pass_at_k(5, 2, 5) == 1.0

    # n=5, c=0, k=1 -> 1 - C(5,1)/C(5,1) = 0.0
    assert compute_pass_at_k(5, 0, 1) == 0.0

    # n=5, c=5, k=3 -> 1 - C(0,3)/C(5,3) = 1.0
    assert compute_pass_at_k(5, 5, 3) == 1.0

    # n=10, c=4, k=3 -> 1 - C(6,3)/C(10,3) = 1 - 20/120 = 5/6
    assert pytest.approx(compute_pass_at_k(10, 4, 3), rel=1e-6) == 5.0 / 6.0


def test_pass_pow_k_hand_calculated():
    # n=5, c=4, k=2 -> C(4,2)/C(5,2) = 6 / 10 = 0.60
    assert pytest.approx(compute_pass_pow_k(5, 4, 2), rel=1e-6) == 0.60

    # n=5, c=3, k=3 -> C(3,3)/C(5,3) = 1 / 10 = 0.10
    assert pytest.approx(compute_pass_pow_k(5, 3, 3), rel=1e-6) == 0.10

    # n=5, c=2, k=3 -> c < k -> 0.0
    assert compute_pass_pow_k(5, 2, 3) == 0.0

    # n=5, c=5, k=5 -> C(5,5)/C(5,5) = 1.0
    assert compute_pass_pow_k(5, 5, 5) == 1.0


def test_mcnemar_exact_hand_calculated():
    # b=0, c=0 -> 1.0
    assert mcnemar_exact_pvalue(0, 0) == 1.0

    # b=1, c=1 -> 1.0
    assert mcnemar_exact_pvalue(1, 1) == 1.0

    # b=0, c=4 -> n=4, k=0: 2 * (0.5)^4 = 2/16 = 0.125
    assert pytest.approx(mcnemar_exact_pvalue(0, 4), rel=1e-6) == 0.125

    # b=0, c=6 -> n=6, k=0: 2 * (0.5)^6 = 2/64 = 0.03125
    assert pytest.approx(mcnemar_exact_pvalue(0, 6), rel=1e-6) == 0.03125

    # b=1, c=5 -> n=6, k=1: 2 * (1 + 6) / 64 = 14/64 = 0.21875
    assert pytest.approx(mcnemar_exact_pvalue(1, 5), rel=1e-6) == 0.21875


def test_bootstrap_ci_deterministic():
    # Constant data
    task_trials = {"t1": [1.0, 1.0, 1.0], "t2": [1.0, 1.0, 1.0]}
    low, high = bootstrap_ci(task_trials, num_samples=500, seed=123)
    assert low == 1.0
    assert high == 1.0

    # Reproducibility with fixed seed
    mixed_data = {"t1": [0.0, 1.0], "t2": [1.0, 1.0]}
    ci1 = bootstrap_ci(mixed_data, num_samples=1000, seed=42)
    ci2 = bootstrap_ci(mixed_data, num_samples=1000, seed=42)
    assert ci1 == ci2
    assert ci1[0] <= ci1[1]


def test_compute_mttif():
    # 3 failures with event indices 10, 20, 30
    trials = [
        {"passed": False, "first_failure": {"event_index": 10}},
        {"passed": False, "first_failure": {"event_index": 20}},
        {"passed": False, "first_failure": {"event_index": 30}},
        {"passed": True, "first_failure": None},
    ]
    mttif = compute_mttif(trials)
    assert mttif == 20.0

    # No failures
    empty_trials = [{"passed": True, "first_failure": None}]
    assert compute_mttif(empty_trials) is None


def test_paired_comparison():
    trials_by_task = {
        "f1_fee_a": [{"trial": 0, "passed": True}, {"trial": 1, "passed": False}],
        "f1_fee_b": [{"trial": 0, "passed": False}, {"trial": 1, "passed": True}],
    }
    res = paired_comparison_a_vs_b(trials_by_task, families=("F1",))
    assert res["b"] == 1  # trial 0: A pass, B fail
    assert res["c"] == 1  # trial 1: A fail, B pass
    assert res["p_value"] == 1.0
    assert res["total_pairs"] == 2


def test_generate_report_pipeline(tmp_path: Path):
    in_dir = tmp_path / "main"
    in_dir.mkdir()
    trials_file = in_dir / "trials.jsonl"
    line1 = (
        '{"model": "m1", "task_id": "f1_fee_a", "trial": 0, "score": 1.0, '
        '"passed": true, "t1": 1.0, "t2": 1.0, "t3": 1.0, "first_failure": null}\n'
    )
    line2 = (
        '{"model": "m1", "task_id": "f1_fee_a", "trial": 1, "score": 0.5, '
        '"passed": false, "t1": 1.0, "t2": 0.5, "t3": 0.0, '
        '"first_failure": {"event_index": 15}}\n'
    )
    trials_file.write_text(line1 + line2)
    out_dir = tmp_path / "summary"
    rep = generate_report(in_dir, out_dir)
    assert len(rep["models"]) == 1
    assert rep["models"][0]["model"] == "m1"
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "summary.md").exists()
