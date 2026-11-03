"""harness/report.py
Report generator aggregating trial results, computing statistical metrics, and generating tables.
See docs/08_HARNESS_AND_STATS.md section 7 and 9.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from harness.stats import (
    bootstrap_ci,
    compute_mttif,
    compute_pass_at_k,
    compute_pass_pow_k,
    paired_comparison_a_vs_b,
)


def load_trials(trials_file: Path, task_filter: Optional[set[str]] = None) -> list[dict[str, Any]]:
    """Load trials from trials.jsonl, filtering by task_filter if provided."""
    trials: list[dict[str, Any]] = []
    if not trials_file.exists():
        return trials
    with open(trials_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if task_filter and rec.get("task_id") not in task_filter:
                    continue
                trials.append(rec)
            except Exception:
                continue
    return trials


def compute_model_summary(model_label: str, trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary statistics for a given model."""
    tasks_dict: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trials:
        tasks_dict[t["task_id"]].append(t)

    task_scores: dict[str, list[float]] = {}
    task_passes: dict[str, int] = {}
    task_trials_count: dict[str, int] = {}
    task_t1: dict[str, list[float]] = defaultdict(list)
    task_t2: dict[str, list[float]] = defaultdict(list)
    task_t3: dict[str, list[float]] = defaultdict(list)

    for task_id, t_list in tasks_dict.items():
        task_scores[task_id] = [t.get("score", 0.0) for t in t_list]
        task_passes[task_id] = sum(1 for t in t_list if t.get("passed", False))
        task_trials_count[task_id] = len(t_list)
        for t in t_list:
            task_t1[task_id].append(t.get("t1", 0.0))
            task_t2[task_id].append(t.get("t2", 0.0))
            task_t3[task_id].append(t.get("t3", 0.0))

    n_tasks = len(tasks_dict)
    if n_tasks == 0:
        return {"model": model_label, "trials_count": 0}

    # Pass rates per task
    task_pass_rates = [
        task_passes[t] / task_trials_count[t]
        for t in tasks_dict if task_trials_count[t] > 0
    ]
    avg_pass_rate = sum(task_pass_rates) / len(task_pass_rates) if task_pass_rates else 0.0

    # pass@k and pass^k where k = median trial count (typically 5)
    counts = [task_trials_count[t] for t in tasks_dict]
    k_val = max(counts) if counts else 1

    pass_at_1_vals = [
        compute_pass_at_k(task_trials_count[t], task_passes[t], 1)
        for t in tasks_dict if task_trials_count[t] > 0
    ]
    pass_at_k_vals = [
        compute_pass_at_k(task_trials_count[t], task_passes[t], min(k_val, task_trials_count[t]))
        for t in tasks_dict if task_trials_count[t] > 0
    ]
    pass_pow_k_vals = [
        compute_pass_pow_k(task_trials_count[t], task_passes[t], min(k_val, task_trials_count[t]))
        for t in tasks_dict if task_trials_count[t] > 0
    ]

    mean_pass_at_1 = sum(pass_at_1_vals) / len(pass_at_1_vals) if pass_at_1_vals else 0.0
    mean_pass_at_k = sum(pass_at_k_vals) / len(pass_at_k_vals) if pass_at_k_vals else 0.0
    mean_pass_pow_k = sum(pass_pow_k_vals) / len(pass_pow_k_vals) if pass_pow_k_vals else 0.0

    # Overall mean score
    all_scores = [t.get("score", 0.0) for t in trials]
    mean_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

    # Tier means
    all_t1 = [t.get("t1", 0.0) for t in trials]
    all_t2 = [t.get("t2", 0.0) for t in trials]
    all_t3 = [t.get("t3", 0.0) for t in trials]
    mean_t1 = sum(all_t1) / len(all_t1) if all_t1 else 0.0
    mean_t2 = sum(all_t2) / len(all_t2) if all_t2 else 0.0
    mean_t3 = sum(all_t3) / len(all_t3) if all_t3 else 0.0

    # MTTIF
    mttif = compute_mttif(trials)

    # Bootstrap CI for mean score and pass rate
    ci_score = bootstrap_ci(task_scores)
    # Boolean pass/fail trials
    task_bool_trials = {
        task_id: [1.0 if t.get("passed", False) else 0.0 for t in t_list]
        for task_id, t_list in tasks_dict.items()
    }
    ci_pass = bootstrap_ci(task_bool_trials)

    # Paired comparison
    paired = paired_comparison_a_vs_b(tasks_dict)

    # Error breakdowns
    format_errors = sum(1 for t in trials if t.get("error") == "FORMAT_ERROR")
    forbidden_imports = sum(1 for t in trials if t.get("error") == "FORBIDDEN_IMPORT")
    missing_files = sum(1 for t in trials if t.get("error") == "MISSING_FILE")

    return {
        "model": model_label,
        "trials_count": len(trials),
        "tasks_count": n_tasks,
        "format_errors": format_errors,
        "forbidden_imports": forbidden_imports,
        "missing_files": missing_files,
        "pass_rate": round(avg_pass_rate, 4),
        "pass_rate_ci95": [round(ci_pass[0], 4), round(ci_pass[1], 4)],
        "pass_at_1": round(mean_pass_at_1, 4),
        f"pass_at_{k_val}": round(mean_pass_at_k, 4),
        f"pass_pow_{k_val}": round(mean_pass_pow_k, 4),
        "mean_score": round(mean_score, 4),
        "mean_score_ci95": [round(ci_score[0], 4), round(ci_score[1], 4)],
        "mean_t1": round(mean_t1, 4),
        "mean_t2": round(mean_t2, 4),
        "mean_t3": round(mean_t3, 4),
        "mttif": round(mttif, 2) if mttif is not None else None,
        "paired_a_vs_b": paired,
    }


def format_markdown_table(summaries: list[dict[str, Any]]) -> str:
    """Format summaries into an ASD-STE100 compliant markdown summary table."""
    lines = [
        "# OrderBook-DST Evaluation Summary",
        "",
        "| Model | Trials | Tasks | Mean Score | 95% CI | Pass Rate | 95% CI | "
        "T1 | T2 | T3 | MTTIF |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        score_ci = f"[{s['mean_score_ci95'][0]:.2f}, {s['mean_score_ci95'][1]:.2f}]"
        pass_ci = f"[{s['pass_rate_ci95'][0]:.2f}, {s['pass_rate_ci95'][1]:.2f}]"
        mttif_str = f"{s['mttif']:.1f}" if s.get("mttif") is not None else "N/A"
        lines.append(
            f"| {s['model']} | {s['trials_count']} | {s['tasks_count']} | "
            f"{s['mean_score']:.2f} | {score_ci} | {s['pass_rate']:.2f} | {pass_ci} | "
            f"{s['mean_t1']:.2f} | {s['mean_t2']:.2f} | {s['mean_t3']:.2f} | {mttif_str} |"
        )
    return "\n".join(lines) + "\n"


def generate_report(
    in_dir: Path, out_dir: Path, task_filter: Optional[set[str]] = None
) -> dict[str, Any]:
    """Load trials, generate summaries, write markdown and json reports."""
    trials_file = in_dir / "trials.jsonl"
    trials = load_trials(trials_file, task_filter=task_filter)

    models_dict: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trials:
        models_dict[t.get("model", "unknown")].append(t)

    summaries = []
    for model_label, model_trials in models_dict.items():
        summaries.append(compute_model_summary(model_label, model_trials))

    overall_paired = paired_comparison_a_vs_b(
        {t["task_id"]: [x for x in trials if x["task_id"] == t["task_id"]] for t in trials}
    )

    report_data = {
        "models": summaries,
        "overall_paired_a_vs_b": overall_paired,
        "total_trials": len(trials),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    md_text = format_markdown_table(summaries)
    (out_dir / "summary.md").write_text(md_text, encoding="utf-8")

    return report_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate benchmark statistical reports.")
    parser.add_argument(
        "--in", dest="in_dir", required=True, help="Input directory containing trials.jsonl"
    )
    parser.add_argument("--out", dest="out_dir", required=True, help="Output directory for reports")
    parser.add_argument(
        "--tasks", dest="tasks", default=None, help="Comma-separated subset of task IDs"
    )
    args = parser.parse_args()

    task_filter = set(args.tasks.split(",")) if args.tasks else None
    in_path = Path(args.in_dir)
    out_path = Path(args.out_dir)

    report_data = generate_report(in_path, out_path, task_filter=task_filter)
    print(format_markdown_table(report_data["models"]))
    print(f"Report written to {out_path / 'summary.md'} and {out_path / 'summary.json'}")


if __name__ == "__main__":
    main()
