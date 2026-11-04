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


def compute_mttif(items: list[Any]) -> Optional[float]:
    """Compute Mean Time To Invariant Failure (MTTIF):
    The mean event index of the first violation over failed seeds.
    Returns None if no failed seeds exist.
    """
    indices: list[int] = []
    for item in items:
        if isinstance(item, (int, float)):
            indices.append(int(item))
        elif isinstance(item, dict):
            # Check for direct event_index or nested first_failure
            if "event_index" in item and isinstance(item["event_index"], (int, float)):
                indices.append(int(item["event_index"]))
            elif "first_failure" in item and isinstance(item["first_failure"], dict):
                ff = item["first_failure"]
                if "event_index" in ff and isinstance(ff["event_index"], (int, float)):
                    indices.append(int(ff["event_index"]))
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


def _family_variant_tasks(
    task_ids: list[str], families: tuple[str, ...]
) -> list[tuple[str, str, str]]:
    """Return (family, task_a, task_b) for families that have both variants."""
    out: list[tuple[str, str, str]] = []
    for fam in families:
        prefix = f"{fam.lower()}_"
        a = next((t for t in sorted(task_ids) if t.startswith(prefix) and t.endswith("_a")), None)
        b = next((t for t in sorted(task_ids) if t.startswith(prefix) and t.endswith("_b")), None)
        if a and b:
            out.append((fam, a, b))
    return out


def family_a_vs_b(
    trials_by_task: dict[str, list[dict[str, Any]]],
    families: tuple[str, ...] = ("F1", "F2", "F3"),
    metric: str = "passed",
    num_permutations: int = 10000,
    seed: int = 42,
) -> dict[str, Any]:
    """Compare Variant A with Variant B within each task family (hypothesis H2).

    Trials of task A and task B are independent model calls on different tasks, so
    they are NOT paired. The test statistic is the mean over families of
    (mean metric on A) - (mean metric on B). The p-value is a one-sided stratified
    permutation test: A/B labels are shuffled within each family, which keeps the
    family mix fixed. `metric` is "passed" (0/1) or "score".

    Only families with both variants enter the comparison (F1-F3). Variant B tasks
    are also longer and touch more state than Variant A, so a positive difference
    measures "A vs B" as designed, not coupling in isolation.
    """
    def val(t: dict[str, Any]) -> float:
        if metric == "passed":
            return 1.0 if t.get("passed", False) else 0.0
        return float(t.get(metric, 0.0))

    groups: list[tuple[str, list[float], list[float]]] = []
    for fam, ta, tb in _family_variant_tasks(list(trials_by_task), families):
        xa = [val(t) for t in trials_by_task[ta]]
        xb = [val(t) for t in trials_by_task[tb]]
        if xa and xb:
            groups.append((fam, xa, xb))

    if not groups:
        return {"metric": metric, "families": [], "mean_diff": None, "p_value": None}

    def stat(gs: list[tuple[str, list[float], list[float]]]) -> float:
        return sum(sum(a) / len(a) - sum(b) / len(b) for _, a, b in gs) / len(gs)

    observed = stat(groups)
    rng = random.Random(seed)
    at_least = 0
    for _ in range(num_permutations):
        shuffled = []
        for fam, xa, xb in groups:
            pool = xa + xb
            rng.shuffle(pool)
            shuffled.append((fam, pool[: len(xa)], pool[len(xa):]))
        if stat(shuffled) >= observed - 1e-12:
            at_least += 1

    return {
        "metric": metric,
        "test": "stratified permutation (one-sided, A > B)",
        "families": [
            {
                "family": fam,
                "n_a": len(xa),
                "n_b": len(xb),
                "mean_a": round(sum(xa) / len(xa), 4),
                "mean_b": round(sum(xb) / len(xb), 4),
                "diff": round(sum(xa) / len(xa) - sum(xb) / len(xb), 4),
            }
            for fam, xa, xb in groups
        ],
        "mean_diff": round(observed, 4),
        "p_value": round((at_least + 1) / (num_permutations + 1), 4),
    }


def paired_tier_gap(
    trials: list[dict[str, Any]], hi: str = "t1", lo: str = "t3"
) -> dict[str, Any]:
    """Within-trial gap between two tiers (hypothesis H1), e.g. T1 - T3.

    The two tiers are scored on the same candidate code, so the difference is
    paired per trial. The CI is the hierarchical (task, then trial) bootstrap.
    Trials that never reached tier 3 (format, import or tier 1/2 errors) are
    excluded, because their tier 3 score is a placeholder 0, not a measurement.
    """
    by_task: dict[str, list[float]] = {}
    for t in trials:
        if t.get("error"):
            continue
        by_task.setdefault(t["task_id"], []).append(
            float(t.get(hi, 0.0)) - float(t.get(lo, 0.0))
        )
    if not by_task:
        return {"n": 0, "mean_gap": None, "ci95": None}
    task_means = [sum(v) / len(v) for v in by_task.values()]
    lo_ci, hi_ci = bootstrap_ci(by_task)
    return {
        "n": sum(len(v) for v in by_task.values()),
        "mean_gap": round(sum(task_means) / len(task_means), 4),
        "ci95": [round(lo_ci, 4), round(hi_ci, 4)],
    }
