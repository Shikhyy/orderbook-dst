"""harness/report.py
Aggregate trial results into the tables and hypothesis metrics the README reports.

Every number in summary.md is computed from trials.jsonl (plus run_meta.json for
model settings). Nothing here is hand-entered.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

from harness.stats import (
    bootstrap_ci,
    compute_mttif,
    compute_pass_at_k,
    compute_pass_pow_k,
    family_a_vs_b,
    mcnemar_exact_pvalue,
    paired_tier_gap,
)

TASK_ORDER = [
    "f1_fee_a", "f1_fee_b", "f2_replace_a", "f2_replace_b",
    "f3_fix_a", "f3_fix_b", "f4_waterfall_b", "f5_basket_b",
]
NUM_HIDDEN_SEEDS = 20
# "Diagnose and fix" tasks (family F9) are exploratory and reported in their own section.
# They are kept out of the headline numbers and out of H1-H5, which are pre-registered for
# the implementation tasks (F1-F8).
DEBUG_TASK_PREFIX = "f9_"
# Labels that mean a conservation / consistency law broke (secondary-state class
# in H5). D1 alone means the reports or final state differ from the reference
# with no invariant broken at that event (primary-logic class).
CONSERVATION_LABELS = {"I1", "I1_ROLLBACK", "I2", "I3", "I4"}
NEAR_MISS_SCORE = 0.9


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


def _variant(task_id: str) -> str:
    return task_id.rsplit("_", 1)[-1].upper()


def _sorted_tasks(task_ids: list[str]) -> list[str]:
    known = [t for t in TASK_ORDER if t in task_ids]
    return known + sorted(t for t in task_ids if t not in TASK_ORDER)


def _failure_class(trial: dict[str, Any]) -> str:
    """One label per failed trial, for the per-task failure table."""
    if trial.get("passed"):
        return "pass"
    err = trial.get("error")
    if err:
        if err in ("FORMAT_ERROR", "MISSING_FILE", "FORBIDDEN_IMPORT", "OUTPUT_TRUNCATED"):
            return err
        if err.startswith("ImportError"):
            return "IMPORT_ERROR"
        if err.startswith("Tier 1 error"):
            return "T1_ERROR"
        if err.startswith("Tier 2 error"):
            return "T2_ERROR"
        return "ERROR"
    ff = trial.get("first_failure")
    if ff:
        return str(ff.get("invariant", "T3_FAIL"))
    if trial.get("t1", 1.0) < 1.0:
        return "T1_FAIL"
    if trial.get("t2", 1.0) < 1.0:
        return "T2_FAIL"
    return "FAIL"


def _seed_label_stats(trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-invariant survival over evaluated hidden seeds (H4) and H5 attribution."""
    evaluated_seeds = 0
    label_seed_counts: Counter[str] = Counter()
    b_fail_seeds = 0
    b_conservation = 0
    b_d1_only = 0
    b_crash = 0
    for t in trials:
        sf = t.get("seed_failures")
        if sf is None or t.get("error"):
            continue
        evaluated_seeds += NUM_HIDDEN_SEEDS
        for f in sf:
            labels = set(f.get("labels", []))
            for lab in labels:
                label_seed_counts[lab] += 1
            if _variant(t["task_id"]) == "B":
                b_fail_seeds += 1
                if labels & CONSERVATION_LABELS:
                    b_conservation += 1
                elif "CRASH" in labels:
                    b_crash += 1
                else:
                    b_d1_only += 1
    survival = {
        inv: round(1.0 - label_seed_counts[inv] / evaluated_seeds, 4) if evaluated_seeds else None
        for inv in ["I1", "I2", "I3", "I4", "D1", "CRASH"]
    }
    return {
        "evaluated_seeds": evaluated_seeds,
        "failing_seed_labels": dict(label_seed_counts),
        "invariant_survival": survival,
        "h5_variant_b": {
            "failing_seeds": b_fail_seeds,
            "conservation_breach": b_conservation,
            "report_or_state_mismatch_only": b_d1_only,
            "crash": b_crash,
            "conservation_share": round(b_conservation / b_fail_seeds, 4) if b_fail_seeds else None,
        },
    }


def compute_model_summary(model_label: str, trials: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary statistics for a given model."""
    tasks_dict: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trials:
        tasks_dict[t["task_id"]].append(t)

    n_tasks = len(tasks_dict)
    if n_tasks == 0:
        return {"model": model_label, "trials_count": 0}

    task_ids = _sorted_tasks(list(tasks_dict))
    counts = {t: len(tasks_dict[t]) for t in task_ids}
    passes = {t: sum(1 for x in tasks_dict[t] if x.get("passed", False)) for t in task_ids}
    k_val = max(counts.values())

    task_pass_rates = [passes[t] / counts[t] for t in task_ids]
    avg_pass_rate = sum(task_pass_rates) / len(task_pass_rates)
    mean_pass_at_1 = sum(compute_pass_at_k(counts[t], passes[t], 1) for t in task_ids) / n_tasks
    mean_pass_at_k = sum(
        compute_pass_at_k(counts[t], passes[t], min(k_val, counts[t])) for t in task_ids
    ) / n_tasks
    mean_pass_pow_k = sum(
        compute_pass_pow_k(counts[t], passes[t], min(k_val, counts[t])) for t in task_ids
    ) / n_tasks

    def mean(key: str, rows: list[dict[str, Any]]) -> float:
        return sum(float(r.get(key, 0.0)) for r in rows) / len(rows) if rows else 0.0

    task_scores = {t: [float(x.get("score", 0.0)) for x in tasks_dict[t]] for t in task_ids}
    task_bool = {
        t: [1.0 if x.get("passed", False) else 0.0 for x in tasks_dict[t]] for t in task_ids
    }
    ci_score = bootstrap_ci(task_scores)
    ci_pass = bootstrap_ci(task_bool)

    per_task = []
    for tid in task_ids:
        rows = tasks_dict[tid]
        classes = Counter(_failure_class(r) for r in rows)
        near = [
            r["trial"] for r in rows
            if not r.get("passed") and float(r.get("score", 0.0)) >= NEAR_MISS_SCORE
        ]
        per_task.append({
            "task_id": tid,
            "variant": _variant(tid),
            "trials": counts[tid],
            "passes": passes[tid],
            f"pass_pow_{k_val}": round(
                compute_pass_pow_k(counts[tid], passes[tid], min(k_val, counts[tid])), 4
            ),
            "mean_score": round(mean("score", rows), 4),
            "mean_t1": round(mean("t1", rows), 4),
            "mean_t2": round(mean("t2", rows), 4),
            "mean_t3": round(mean("t3", rows), 4),
            "outcomes": dict(classes),
            "near_miss_trials": near,
        })

    costs = [float(t.get("cost_usd_est", 0.0) or 0.0) for t in trials]
    lat = [float(t.get("latency_s", 0.0) or 0.0) for t in trials]
    first = trials[0]

    return {
        "model": model_label,
        "model_id": first.get("model_id"),
        "tier": first.get("tier"),
        "served_model": first.get("served_model"),
        "settings": first.get("settings"),
        "trials_count": len(trials),
        "tasks_count": n_tasks,
        "trials_per_task": k_val,
        "format_errors": sum(1 for t in trials if t.get("error") == "FORMAT_ERROR"),
        "forbidden_imports": sum(1 for t in trials if t.get("error") == "FORBIDDEN_IMPORT"),
        "missing_files": sum(1 for t in trials if t.get("error") == "MISSING_FILE"),
        "output_truncated": sum(1 for t in trials if t.get("error") == "OUTPUT_TRUNCATED"),
        "prompt_truncated_suspected": sum(1 for t in trials if t.get("prompt_truncated_suspected")),
        "pass_rate": round(avg_pass_rate, 4),
        "pass_rate_ci95": [round(ci_pass[0], 4), round(ci_pass[1], 4)],
        "pass_at_1": round(mean_pass_at_1, 4),
        f"pass_at_{k_val}": round(mean_pass_at_k, 4),
        f"pass_pow_{k_val}": round(mean_pass_pow_k, 4),
        "mean_score": round(mean("score", trials), 4),
        "mean_score_ci95": [round(ci_score[0], 4), round(ci_score[1], 4)],
        "mean_t1": round(mean("t1", trials), 4),
        "mean_t2": round(mean("t2", trials), 4),
        "mean_t3": round(mean("t3", trials), 4),
        "mttif": (lambda v: round(v, 2) if v is not None else None)(compute_mttif(trials)),
        "total_cost_usd": round(sum(costs), 4),
        "mean_latency_s": round(sum(lat) / len(lat), 2) if lat else None,
        "per_task": per_task,
        "h1_t1_minus_t3": paired_tier_gap(trials, "t1", "t3"),
        "h2_a_vs_b_pass": family_a_vs_b(tasks_dict, metric="passed"),
        "h2_a_vs_b_score": family_a_vs_b(tasks_dict, metric="score"),
        "seed_stats": _seed_label_stats(trials),
    }


def _is_debug_task(task_id: Any) -> bool:
    return str(task_id).startswith(DEBUG_TASK_PREFIX)


def _graded_as(task_id: str) -> Optional[str]:
    """The task a diagnose-and-fix task is graded as (its `grades_as`), if readable."""
    try:
        import tomllib as tomli
    except ImportError:  # pragma: no cover
        import tomli  # type: ignore
    toml_path = Path(__file__).resolve().parent.parent / "tasks" / task_id / "task.toml"
    try:
        return str(tomli.loads(toml_path.read_text(encoding="utf-8")).get("grades_as") or "")
    except Exception:
        return None


def compute_debug_summary(
    debug_trials: list[dict[str, Any]], impl_trials: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Per model and F9 task: passes, mean score, and the same model on the base task."""
    by_model: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for t in debug_trials:
        by_model[t.get("model", "unknown")][t["task_id"]].append(t)
    impl_by: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for t in impl_trials:
        impl_by[(t.get("model", "unknown"), t["task_id"])].append(t)
    out = []
    for model, tasks in by_model.items():
        rows = []
        for tid in sorted(tasks):
            tr = tasks[tid]
            base = _graded_as(tid)
            base_rows = impl_by.get((model, base or ""), [])
            rows.append({
                "task_id": tid,
                "graded_as": base,
                "trials": len(tr),
                "passes": sum(1 for x in tr if x.get("passed", False)),
                "mean_score": round(sum(float(x.get("score", 0.0)) for x in tr) / len(tr), 4),
                "outcomes": dict(Counter(_failure_class(x) for x in tr)),
                "base_trials": len(base_rows),
                "base_passes": sum(1 for x in base_rows if x.get("passed", False)),
            })
        out.append({"model": model, "tasks": rows})
    return out


TIER_RANK = {"small": 0, "mid": 1, "frontier": 2}


def sanity_checks(summaries: list[dict[str, Any]]) -> list[str]:
    """Warnings from the guide's 'models fail for real reasons' checks."""
    rows = [s for s in summaries if s.get("trials_count")]
    if not rows:
        return []
    warns: list[str] = []
    if all(s["pass_rate"] == 0.0 for s in rows):
        warns.append("Every model has a 0% pass rate. This is more often a broken task, prompt or "
                     "grader than an impossible capability: check the specs and reference first.")
    best = max(rows, key=lambda s: s["pass_rate"])
    if best["pass_rate"] >= 0.9:
        warns.append(f"Little headroom: {best['model']} passes {best['pass_rate']:.0%} of trials. "
                     "The eval may no longer show a limitation for this model.")
    for a in rows:
        for b in rows:
            ra, rb = TIER_RANK.get(a.get("tier") or ""), TIER_RANK.get(b.get("tier") or "")
            if ra is not None and rb is not None and ra < rb and a["mean_score"] > b["mean_score"]:
                warns.append(f"{a['model']} (tier {a['tier']}) outscores {b['model']} (tier "
                             f"{b['tier']}): {a['mean_score']:.3f} vs {b['mean_score']:.3f}. Look "
                             "for ambiguity or grader problems before reporting this as a finding.")
    tasks = sorted({p["task_id"] for s in rows for p in s["per_task"]})
    for tid in tasks:
        cells = [p for s in rows for p in s["per_task"] if p["task_id"] == tid]
        if cells and all(p["passes"] == p["trials"] for p in cells):
            warns.append(f"`{tid}` is passed by every trial of every model: it does not separate "
                         "models.")
        if cells and all(p["passes"] == 0 and p["mean_score"] < 0.2 for p in cells):
            warns.append(f"`{tid}` is failed badly by every model: re-check its instruction and "
                         "reference before claiming a limitation.")
    for s in rows:
        fmt = s["format_errors"] + s["missing_files"]
        if fmt / s["trials_count"] > 0.2:
            warns.append(f"{s['model']}: {fmt} of {s['trials_count']} trials had no usable file "
                         "block. That measures output formatting, not the task; check the replies.")
        cut = s.get("output_truncated", 0)
        if cut:
            warns.append(f"{s['model']}: {cut} trials ran out of output tokens before giving an "
                         "answer (reasoning models can spend the whole budget thinking). Raise "
                         "max_tokens in models.toml if the provider allows it, then re-run those "
                         "trials; report the remaining ones as a token-budget limit.")
        trunc = s.get("prompt_truncated_suspected", 0)
        if trunc:
            warns.append(f"{s['model']}: {trunc} trials look like the prompt was truncated by a "
                         "small context window; those failures are not about the task. Raise the "
                         "context length and re-run them.")
        expected = s["tasks_count"] * s["trials_per_task"]
        if s["trials_count"] < expected:
            warns.append(f"{s['model']}: {s['trials_count']} of {expected} trials recorded; the "
                         "run is incomplete (resume it).")
    return warns


def compute_feedback_summary(model_label: str, trials: list[dict[str, Any]]) -> dict[str, Any]:
    """H3: first attempt (turn 0) vs final attempt on the same trial (paired)."""
    pairs = []
    for t in trials:
        turns = t.get("turns") or []
        if not turns:
            continue
        pairs.append((turns[0], turns[-1], t))
    if not pairs:
        return {"model": model_label, "trials": 0}
    first_pass = [bool(a.get("passed")) for a, _, _ in pairs]
    final_pass = [bool(b.get("passed")) for _, b, _ in pairs]
    b = sum(1 for x, y in zip(first_pass, final_pass) if x and not y)
    c = sum(1 for x, y in zip(first_pass, final_pass) if not x and y)
    gains = [float(z.get("score", 0.0)) - float(a.get("score", 0.0)) for a, z, _ in pairs]
    return {
        "model": model_label,
        "trials": len(pairs),
        "turn0_pass_rate": round(sum(first_pass) / len(pairs), 4),
        "final_pass_rate": round(sum(final_pass) / len(pairs), 4),
        "turn0_mean_score": round(
            sum(float(a.get("score", 0)) for a, _, _ in pairs) / len(pairs), 4
        ),
        "final_mean_score": round(
            sum(float(z.get("score", 0)) for _, z, _ in pairs) / len(pairs), 4
        ),
        "mean_score_gain": round(sum(gains) / len(gains), 4),
        "mcnemar_b_fixed_to_broken": b,
        "mcnemar_c_broken_to_fixed": c,
        "mcnemar_p": round(mcnemar_exact_pvalue(b, c), 4),
        "mean_revisions": round(
            sum(len(t.get("turns", [])) - 1 for _, _, t in pairs) / len(pairs), 2
        ),
    }


def _fmt(v: Optional[float], spec: str = ".2f") -> str:
    return "–" if v is None else format(v, spec)


def _fmt_ci(ci: Optional[list[float]]) -> str:
    return "–" if not ci else f"[{ci[0]:.2f}, {ci[1]:.2f}]"


def format_markdown_table(summaries: list[dict[str, Any]]) -> str:
    """Headline table in the format the hackathon guide asks for."""
    lines = [
        "| Model (ID, settings) | Trials / task | Pass rate | 95% CI | pass@k | pass^k | "
        "Mean score | 95% CI | T1 | T2 | T3 | Cost (run) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        if not s.get("trials_count"):
            continue
        k = s["trials_per_task"]
        settings = s.get("settings") or {}
        set_str = ", ".join(
            f"{a}={b}" for a, b in settings.items() if a != "base_url"
        ) or "defaults"
        lines.append(
            f"| **{s['model']}** (`{s.get('model_id')}`, {set_str}) | {k} | "
            f"{s['pass_rate']:.1%} | {_fmt_ci(s['pass_rate_ci95'])} | "
            f"{s[f'pass_at_{k}']:.1%} | {s[f'pass_pow_{k}']:.1%} | "
            f"{s['mean_score']:.3f} | {_fmt_ci(s['mean_score_ci95'])} | "
            f"{s['mean_t1']:.2f} | {s['mean_t2']:.2f} | {s['mean_t3']:.2f} | "
            f"${s['total_cost_usd']:.2f} |"
        )
    return "\n".join(lines) + "\n"


def format_full_markdown(report: dict[str, Any]) -> str:
    summaries = [s for s in report["models"] if s.get("trials_count")]
    out = ["# OrderBook-DST Evaluation Summary", ""]
    meta = report.get("run_meta") or {}
    if meta:
        out += [
            f"- Run date (UTC): {meta.get('date', '–')}",
            f"- Git SHA: `{meta.get('git_sha', '–')}`",
            f"- Total trials: {report['total_trials']}",
            "",
        ]
    out += ["## Headline results", "", format_markdown_table(summaries)]
    out += [
        "Pass = score 1.0 (all public tests, all checkpoints and all 20 hidden seeds). "
        "pass@k: at least one of k trials passes; pass^k: all k pass. CIs are a "
        "hierarchical bootstrap over tasks, then trials. Cost uses the per-model "
        "prices in `models.toml` (0 if not set).",
        "",
        "## Per-task results (passes / trials, mean score)",
        "",
    ]
    tasks = _sorted_tasks(sorted({p["task_id"] for s in summaries for p in s["per_task"]}))
    out.append("| Task | " + " | ".join(s["model"] for s in summaries) + " |")
    out.append("|---|" + "---|" * len(summaries))
    for tid in tasks:
        cells = []
        for s in summaries:
            p = next((x for x in s["per_task"] if x["task_id"] == tid), None)
            cells.append("–" if not p else f"{p['passes']}/{p['trials']} ({p['mean_score']:.2f})")
        out.append(f"| `{tid}` | " + " | ".join(cells) + " |")

    out += ["", "## Outcome of each trial by task", "",
            "First failure per trial: invariant ID (I1–I4), D1 = report/state differs "
            "from reference, T1/T2 = failed visible tests or checkpoints, or an "
            "extraction/import error.", ""]
    for s in summaries:
        out.append(f"**{s['model']}**")
        out.append("")
        for p in s["per_task"]:
            oc = ", ".join(f"{k}×{v}" for k, v in sorted(p["outcomes"].items()))
            near = f" — near miss trials: {p['near_miss_trials']}" if p["near_miss_trials"] else ""
            out.append(f"- `{p['task_id']}`: {oc}{near}")
        out.append("")

    warns = report.get("sanity_checks") or []
    out += ["## Sanity checks", ""]
    out += [f"- ⚠️ {w}" for w in warns] if warns else ["- No warnings."]
    out.append("")

    out += ["## Pre-registered hypotheses (computed; see HYPOTHESES.md)", ""]
    out.append("| Model | H1: T1 − T3 [95% CI] | H2: A − B pass rate (p) | "
               "H2: A − B score (p) | H4: I1 / I2 seed survival | "
               "H5: conservation share of B failing seeds |")
    out.append("|---|---|---|---|---|---|")
    for s in summaries:
        h1 = s["h1_t1_minus_t3"]
        h2p, h2s = s["h2_a_vs_b_pass"], s["h2_a_vs_b_score"]
        surv = s["seed_stats"]["invariant_survival"]
        h5 = s["seed_stats"]["h5_variant_b"]
        out.append(
            f"| {s['model']} | {_fmt(h1['mean_gap'], '.3f')} {_fmt_ci(h1['ci95'])} | "
            f"{_fmt(h2p['mean_diff'], '.3f')} (p={_fmt(h2p['p_value'], '.3f')}) | "
            f"{_fmt(h2s['mean_diff'], '.3f')} (p={_fmt(h2s['p_value'], '.3f')}) | "
            f"{_fmt(surv['I1'], '.2f')} / {_fmt(surv['I2'], '.2f')} | "
            f"{_fmt(h5['conservation_share'], '.0%')} of {h5['failing_seeds']} |"
        )
    out += [
        "",
        "- H1 is paired within each trial; trials with extraction or tier 1/2 errors are excluded.",
        "- H2 uses only families with both variants (F1–F3) and a one-sided stratified "
        "permutation test. A and B are different tasks, so this is not a paired test, and "
        "B tasks are also larger, so the gap is not attributable to coupling alone.",
        "- H4/H5 use every failing hidden seed, with all labels seen at its first failing "
        "event. H5's split (conservation law broken vs report mismatch only) is an "
        "automatic proxy for the pre-registered 'secondary omission vs primary logic' "
        "classification and must be checked against the transcripts.",
        "",
    ]
    debug = report.get("debug") or []
    if debug:
        out += ["## F9: diagnose and fix (exploratory; not part of H1–H5)", "",
                "The model gets the specification, a handler with one defect and the first "
                "failing step of a short trace, and returns the corrected file. Each task is "
                "graded exactly like the task it is graded as. These trials are not in the "
                "headline table or in H1–H5. `impl` is the same model's passes on the "
                "implementation task (written from scratch) that the F9 task is graded as.", ""]
        tids = sorted({r["task_id"] for d in debug for r in d["tasks"]})
        out.append("| Task (graded as) | " + " | ".join(d["model"] for d in debug) + " |")
        out.append("|---|" + "---|" * len(debug))
        for tid in tids:
            cells = []
            graded_as = ""
            for d in debug:
                r = next((x for x in d["tasks"] if x["task_id"] == tid), None)
                if r is None:
                    cells.append("–")
                    continue
                graded_as = r["graded_as"] or ""
                impl = f", impl {r['base_passes']}/{r['base_trials']}" if r["base_trials"] else ""
                cells.append(f"{r['passes']}/{r['trials']} ({r['mean_score']:.2f}){impl}")
            out.append(f"| `{tid}` (`{graded_as}`) | " + " | ".join(cells) + " |")
        out.append("")
    fb = [f for f in report.get("feedback", []) if f.get("trials")]
    if fb:
        out += ["## H3: invariant feedback loop (paired: same trial, first vs final turn)", "",
                "| Model | Trials | Turn 0 pass | Final pass | Mean score gain | "
                "Fixed / broken | McNemar p | Mean revisions |",
                "|---|---|---|---|---|---|---|---|"]
        for f in fb:
            out.append(
                f"| {f['model']} | {f['trials']} | {f['turn0_pass_rate']:.1%} | "
                f"{f['final_pass_rate']:.1%} | {f['mean_score_gain']:+.3f} | "
                f"{f['mcnemar_c_broken_to_fixed']} / {f['mcnemar_b_fixed_to_broken']} | "
                f"{f['mcnemar_p']:.3f} | {f['mean_revisions']:.2f} |"
            )
        out.append("")
    return "\n".join(out)


def generate_report(
    in_dir: Path, out_dir: Path, task_filter: Optional[set[str]] = None
) -> dict[str, Any]:
    """Load trials, generate summaries, write markdown and json reports."""
    all_trials = load_trials(in_dir / "trials.jsonl", task_filter=task_filter)
    trials = [t for t in all_trials if not _is_debug_task(t.get("task_id"))]
    debug_trials = [
        t for t in all_trials
        if _is_debug_task(t.get("task_id")) and t.get("mode") != "feedback_loop"
    ]
    meta_file = in_dir / "run_meta.json"
    run_meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}

    single: dict[str, list[dict[str, Any]]] = defaultdict(list)
    feedback: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trials:
        target = feedback if t.get("mode") == "feedback_loop" else single
        target[t.get("model", "unknown")].append(t)

    report_data: dict[str, Any] = {
        "models": [compute_model_summary(m, rows) for m, rows in single.items()],
        "feedback": [compute_feedback_summary(m, rows) for m, rows in feedback.items()],
        "total_trials": len(all_trials),
        "debug": compute_debug_summary(
            debug_trials, [t for t in trials if t.get("mode") != "feedback_loop"]
        ),
        "run_meta": {k: run_meta.get(k) for k in ("date", "git_sha", "models")},
    }
    # Feedback-loop trials also have a final single score; summarise those too.
    if not report_data["models"] and feedback:
        report_data["models"] = [compute_model_summary(m, rows) for m, rows in feedback.items()]
    report_data["sanity_checks"] = sanity_checks(report_data["models"])

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(format_full_markdown(report_data), encoding="utf-8")
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
    print(format_full_markdown(report_data))
    print(f"Report written to {out_path / 'summary.md'} and {out_path / 'summary.json'}")


if __name__ == "__main__":
    main()
