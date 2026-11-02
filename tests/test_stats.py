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
    # Formula from docs/08 section 9: pass@k = 1 - C(n-c, k) / C(n, k)
    #
    # Case 1: n=5, c=2, k=1
    # C(5-2, 1) = C(3, 1) = 3
    # C(5, 1) = 5
    # pass@1 = 1 - (3 / 5) = 1 - 0.60 = 0.40
    assert pytest.approx(compute_pass_at_k(5, 2, 1), rel=1e-6) == 0.40

    # Case 2: n=5, c=2, k=2
    # C(5-2, 2) = C(3, 2) = 3
    # C(5, 2) = 10
    # pass@2 = 1 - (3 / 10) = 1 - 0.30 = 0.70
    assert pytest.approx(compute_pass_at_k(5, 2, 2), rel=1e-6) == 0.70

    # Case 3: n=5, c=2, k=3
    # C(5-2, 3) = C(3, 3) = 1
    # C(5, 3) = 10
    # pass@3 = 1 - (1 / 10) = 1 - 0.10 = 0.90
    assert pytest.approx(compute_pass_at_k(5, 2, 3), rel=1e-6) == 0.90

    # Case 4: n=5, c=2, k=5
    # n - c = 3 < k=5 -> any subset of size 5 contains at least one passing trial -> 1.0
    assert compute_pass_at_k(5, 2, 5) == 1.0

    # Case 5: n=5, c=0, k=1
    # C(5, 1) / C(5, 1) = 1 -> pass@1 = 1 - 1 = 0.0
    assert compute_pass_at_k(5, 0, 1) == 0.0

    # Case 6: n=5, c=5, k=3
    # C(0, 3) = 0 -> pass@3 = 1 - 0 = 1.0
    assert compute_pass_at_k(5, 5, 3) == 1.0

    # Case 7: n=10, c=4, k=3
    # C(10-4, 3) = C(6, 3) = (6 * 5 * 4) / (3 * 2 * 1) = 20
    # C(10, 3) = (10 * 9 * 8) / (3 * 2 * 1) = 120
    # pass@3 = 1 - (20 / 120) = 1 - 1/6 = 5/6 = 0.833333...
    assert pytest.approx(compute_pass_at_k(10, 4, 3), rel=1e-6) == 5.0 / 6.0


def test_pass_pow_k_hand_calculated():
    # Formula from docs/08 section 9: pass^k = C(c, k) / C(n, k)
    # Note: this is NOT (c / n)^k.
    #
    # Case 1: n=5, c=4, k=2
    # C(4, 2) = (4 * 3) / 2 = 6
    # C(5, 2) = (5 * 4) / 2 = 10
    # pass^2 = 6 / 10 = 0.60
    # Contrast with naive (c/n)^k = (4/5)^2 = 16/25 = 0.64 (differs by 0.04)
    assert pytest.approx(compute_pass_pow_k(5, 4, 2), rel=1e-6) == 0.60

    # Case 2: n=5, c=3, k=3
    # C(3, 3) = 1
    # C(5, 3) = 10
    # pass^3 = 1 / 10 = 0.10
    # Contrast with naive (c/n)^k = (3/5)^3 = 27/125 = 0.216 (differs by 0.116)
    assert pytest.approx(compute_pass_pow_k(5, 3, 3), rel=1e-6) == 0.10

    # Case 3: n=5, c=2, k=3
    # c=2 < k=3: impossible to draw 3 passes out of 2 -> 0.0
    assert compute_pass_pow_k(5, 2, 3) == 0.0

    # Case 4: n=5, c=5, k=5
    # C(5, 5) / C(5, 5) = 1 / 1 = 1.0
    assert compute_pass_pow_k(5, 5, 5) == 1.0

    # Case 5: n=6, c=4, k=3
    # C(4, 3) = 4
    # C(6, 3) = (6 * 5 * 4) / (3 * 2 * 1) = 20
    # pass^3 = 4 / 20 = 0.20
    assert pytest.approx(compute_pass_pow_k(6, 4, 3), rel=1e-6) == 0.20


def test_mcnemar_exact_hand_calculated():
    # Formula: exact binomial test for discordant pairs (b, c) with p=0.5
    #
    # Case 1: b=0, c=0 -> 1.0
    assert mcnemar_exact_pvalue(0, 0) == 1.0

    # Case 2: b=1, c=1 -> 1.0
    assert mcnemar_exact_pvalue(1, 1) == 1.0

    # Case 3: b=0, c=4 -> n_disc = 4, k = min(0, 4) = 0
    # P(X = 0) = C(4, 0) * (0.5)^4 = 1 / 16 = 0.0625
    # Two-sided p-value = 2 * 0.0625 = 0.125
    assert pytest.approx(mcnemar_exact_pvalue(0, 4), rel=1e-6) == 0.125

    # Case 4: b=0, c=6 -> n_disc = 6, k = min(0, 6) = 0
    # P(X = 0) = C(6, 0) * (0.5)^6 = 1 / 64 = 0.015625
    # Two-sided p-value = 2 * 0.015625 = 0.03125
    assert pytest.approx(mcnemar_exact_pvalue(0, 6), rel=1e-6) == 0.03125

    # Case 5: b=1, c=5 -> n_disc = 6, k = min(1, 5) = 1
    # P(X <= 1) = (C(6, 0) + C(6, 1)) * (0.5)^6 = (1 + 6) / 64 = 7 / 64 = 0.109375
    # Two-sided p-value = 2 * 0.109375 = 14 / 64 = 0.21875
    assert pytest.approx(mcnemar_exact_pvalue(1, 5), rel=1e-6) == 0.21875


def test_bootstrap_ci_deterministic():
    # Hand calculation 1: Constant data
    # When all tasks and all trials have identical value 1.0, every resampled task
    # and every resampled trial evaluates to 1.0. Mean metric must be exactly 1.0.
    task_trials = {"t1": [1.0, 1.0, 1.0], "t2": [1.0, 1.0, 1.0]}
    low, high = bootstrap_ci(task_trials, num_samples=10000, seed=42)
    assert low == 1.0
    assert high == 1.0

    # Hand calculation 2: Reproducibility with fixed seed and 10,000 resamples
    # Hierarchical bootstrap resamples tasks with replacement, then trials with replacement.
    mixed_data = {"t1": [0.0, 1.0], "t2": [1.0, 1.0]}
    ci1 = bootstrap_ci(mixed_data, num_samples=10000, seed=42)
    ci2 = bootstrap_ci(mixed_data, num_samples=10000, seed=42)
    assert ci1 == ci2
    assert 0.0 <= ci1[0] <= ci1[1] <= 1.0


def test_compute_mttif_hand_calculated():
    # Formula from docs/08 section 9:
    # MTTIF = Mean event index of the first violation over failed seeds.
    #
    # Hand calculation 1: List of raw event indices from failed seeds:
    # Seed A failed at event index 45
    # Seed B failed at event index 80
    # Seed C failed at event index 125
    # Mean = (45 + 80 + 125) / 3 = 250 / 3 = 83.33333333333333
    failed_seed_indices = [45, 80, 125]
    mttif_raw = compute_mttif(failed_seed_indices)
    assert pytest.approx(mttif_raw, rel=1e-6) == 250.0 / 3.0

    # Hand calculation 2: From trial records with first_failure event_index
    # Trial 1: first failure event 10
    # Trial 2: first failure event 20
    # Trial 3: first failure event 30
    # Trial 4: passed (no failure, ignored in MTTIF)
    # Mean = (10 + 20 + 30) / 3 = 60 / 3 = 20.0
    trials = [
        {"passed": False, "first_failure": {"event_index": 10}},
        {"passed": False, "first_failure": {"event_index": 20}},
        {"passed": False, "first_failure": {"event_index": 30}},
        {"passed": True, "first_failure": None},
    ]
    mttif_trials = compute_mttif(trials)
    assert mttif_trials == 20.0

    # No failed seeds -> returns None
    empty_trials = [{"passed": True, "first_failure": None}]
    assert compute_mttif(empty_trials) is None
    assert compute_mttif([]) is None


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
