"""harness/stats.py
Statistical evaluation metrics, bootstrap confidence intervals, and paired comparisons.
See docs/08_HARNESS_AND_STATS.md section 9.
"""
import math
import random
from typing import Any, Callable, Optional


def compute_pass_at_k(n: int, c: int, k: int) -> float:
    """Compute pass@k unbiased estimator: 1 - C(n-c, k) / C(n, k).

    If n - c < k, all subsets of size k contain at least one passing trial.
    """
    if k <= 0 or n <= 0 or k > n or c < 0 or c > n:
        return 0.0
    if n - c < k:
        return 1.0
    num = math.comb(n - c, k)
    denom = math.comb(n, k)
    return 1.0 - (num / denom)


def compute_pass_pow_k(n: int, c: int, k: int) -> float:
    """Compute pass^k metric: C(c, k) / C(n, k).

    Probability that all k drawn trials pass.
    """
    if k <= 0 or n <= 0 or k > n or c < 0 or c > n or c < k:
        return 0.0
    num = math.comb(c, k)
    denom = math.comb(n, k)
    return num / denom


def compute_mttif(trials: list[dict[str, Any]]) -> Optional[float]:
    """Compute Mean Time To Invariant Failure (MTTIF):

    Average event index of the first invariant violation over failed trials.
    Returns None if no trial has a recorded first failure event index.
    """
    indices: list[int] = []
    for t in trials:
        first_fail = t.get("first_failure")
        if first_fail and isinstance(first_fail, dict) and "event_index" in first_fail:
            idx = first_fail["event_index"]
            if idx is not None and isinstance(idx, (int, float)):
                indices.append(int(idx))
    if not indices:
        return None
    return sum(indices) / len(indices)


def bootstrap_ci(
    task_trials: dict[str, list[float]],
    metric_fn: Callable[[list[float]], float] = lambda x: sum(x) / len(x) if x else 0.0,
    num_samples: int = 10000,
    seed: int = 42,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Compute hierarchical bootstrap confidence interval over tasks and trials.

    1. Resample tasks with replacement.
    2. For each sampled task, resample its trials with replacement.
    3. Compute the task scores and apply metric_fn across task scores.
    4. Repeat num_samples times with fixed seed.
    5. Return (lower, upper) percentiles.
    """
    if not task_trials:
        return (0.0, 0.0)

    task_keys = sorted(task_trials.keys())
    rng = random.Random(seed)
    n_tasks = len(task_keys)

    estimates: list[float] = []

    for _ in range(num_samples):
        # 1. Resample tasks with replacement
        sampled_task_keys = [task_keys[rng.randint(0, n_tasks - 1)] for _ in range(n_tasks)]

        sample_task_scores: list[float] = []
        for t_key in sampled_task_keys:
            trials = task_trials[t_key]
            n_tr = len(trials)
            if n_tr == 0:
                sample_task_scores.append(0.0)
            else:
                # 2. Resample trials for this task with replacement
                resampled_trials = [trials[rng.randint(0, n_tr - 1)] for _ in range(n_tr)]
                sample_task_scores.append(sum(resampled_trials) / n_tr)

        # 3. Compute metric over task scores
        estimates.append(metric_fn(sample_task_scores))

    estimates.sort()
    low_idx = int(num_samples * (alpha / 2.0))
    high_idx = int(num_samples * (1.0 - alpha / 2.0))
    high_idx = min(high_idx, num_samples - 1)

    return (estimates[low_idx], estimates[high_idx])


def mcnemar_exact_pvalue(b: int, c: int) -> float:
    """Compute exact two-sided McNemar test p-value for discordant pairs (b, c).

    Under H0: b ~ Binomial(b + c, 0.5).
    """
    n_disc = b + c
    if n_disc == 0:
        return 1.0

    k = min(b, c)
    # Sum binomial probabilities for x in 0..k with p=0.5
    cum_prob = sum(math.comb(n_disc, i) * (0.5 ** n_disc) for i in range(k + 1))
    p_value = min(1.0, 2.0 * cum_prob)
    return p_value


def paired_comparison_a_vs_b(
    trials_by_task: dict[str, list[dict[str, Any]]],
    families: tuple[str, ...] = ("F1", "F2", "F3"),
) -> dict[str, Any]:
    """Perform paired comparison between variant A and variant B.

    Matches trial index t for task A and task B in each family.
    Returns discordant pair counts b (A pass, B fail), c (A fail, B pass), and exact p-value.
    """
    b = 0
    c = 0
    pairs: list[tuple[str, int, bool, bool]] = []

    for fam in families:
        fam_lower = fam.lower()
        # Find tasks matching fam_lower + "_..._a" and fam_lower + "_..._b"
        task_a = None
        task_b = None
        for t_id in trials_by_task:
            if t_id.startswith(f"{fam_lower}_") and t_id.endswith("_a"):
                task_a = t_id
            elif t_id.startswith(f"{fam_lower}_") and t_id.endswith("_b"):
                task_b = t_id

        if not task_a or not task_b:
            continue

        trials_a = {
            t.get("trial", idx): t.get("passed", False)
            for idx, t in enumerate(trials_by_task[task_a])
        }
        trials_b = {
            t.get("trial", idx): t.get("passed", False)
            for idx, t in enumerate(trials_by_task[task_b])
        }

        common_trials = sorted(set(trials_a.keys()).intersection(trials_b.keys()))
        for tr in common_trials:
            pass_a = bool(trials_a[tr])
            pass_b = bool(trials_b[tr])
            pairs.append((fam, tr, pass_a, pass_b))
            if pass_a and not pass_b:
                b += 1
            elif not pass_a and pass_b:
                c += 1

    return {
        "b": b,
        "c": c,
        "p_value": mcnemar_exact_pvalue(b, c),
        "total_pairs": len(pairs),
    }
