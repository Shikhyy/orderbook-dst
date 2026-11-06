"""tools/human_audit.py
Human audit tool for OrderBook-DST benchmark.
See docs/07_GRADER_SPEC.md section 9.

Samples 20 stored trials (10 pass, 10 fail) with a fixed seed, blinds the grader
outcome, collects author verdicts, prints a 2x2 agreement matrix with Cohen's
kappa, and writes results to results/human_audit.md.
"""
import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


def compute_cohens_kappa(
    grader_verdicts: list[bool], human_verdicts: list[bool]
) -> tuple[float, dict[str, int]]:
    """Compute Cohen's kappa agreement statistic between grader and human."""
    if len(grader_verdicts) != len(human_verdicts) or not grader_verdicts:
        return 0.0, {"TP": 0, "FP": 0, "TN": 0, "FN": 0}

    n = len(grader_verdicts)
    tp = sum(1 for g, h in zip(grader_verdicts, human_verdicts) if g and h)
    tn = sum(1 for g, h in zip(grader_verdicts, human_verdicts) if not g and not h)
    fp = sum(1 for g, h in zip(grader_verdicts, human_verdicts) if g and not h)
    fn = sum(1 for g, h in zip(grader_verdicts, human_verdicts) if not g and h)

    matrix = {"TP": tp, "FP": fp, "TN": tn, "FN": fn}

    po = (tp + tn) / n
    p_grader_pass = (tp + fp) / n
    p_grader_fail = (tn + fn) / n
    p_human_pass = (tp + fn) / n
    p_human_fail = (tn + fp) / n

    pe = (p_grader_pass * p_human_pass) + (p_grader_fail * p_human_fail)

    if pe >= 1.0:
        kappa = 1.0
    else:
        kappa = (po - pe) / (1.0 - pe)

    return round(kappa, 4), matrix


def sample_trials(
    trials: list[dict[str, Any]],
    n_pass: int = 10,
    n_fail: int = 10,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Select n_pass passed and n_fail failed trials using a fixed seed."""
    rng = random.Random(seed)

    passes = [t for t in trials if t.get("passed", False)]
    fails = [t for t in trials if not t.get("passed", False)]

    # Sort deterministically before shuffling
    passes.sort(
        key=lambda x: (
            x.get("model", ""),
            x.get("task_id", ""),
            x.get("trial", 0),
        )
    )
    fails.sort(
        key=lambda x: (
            x.get("model", ""),
            x.get("task_id", ""),
            x.get("trial", 0),
        )
    )

    rng.shuffle(passes)
    rng.shuffle(fails)

    sampled_pass = passes[:n_pass]
    sampled_fail = fails[:n_fail]

    combined = sampled_pass + sampled_fail
    rng.shuffle(combined)
    return combined


def load_candidate_code(
    raw_dir: Path, model: str, task_id: str, trial: int
) -> str:
    """Retrieve candidate code from raw trial files folder."""
    trial_files = raw_dir / model / task_id / str(trial) / "files"
    if not trial_files.exists():
        return "(Candidate code files not found on disk)"

    snippets = []
    for p in sorted(trial_files.rglob("*.py")):
        rel = p.relative_to(trial_files)
        snippets.append(f"--- File: {rel} ---\n{p.read_text(encoding='utf-8')}")

    return "\n\n".join(snippets) if snippets else "(No python files found)"


NO_CODE_ERRORS = ("OUTPUT_TRUNCATED", "FORMAT_ERROR")


def is_judgeable(trial: dict[str, Any], raw_dir: Path) -> bool:
    """A trial can be judged by a human only if it produced code to read.

    Truncated or malformed replies have no Python file, so a human verdict on them would
    trivially agree with the grader and inflate kappa.
    """
    err = str(trial.get("error") or "")
    if any(err.startswith(e) for e in NO_CODE_ERRORS):
        return False
    files = (
        raw_dir
        / trial.get("model", "")
        / trial.get("task_id", "")
        / str(trial.get("trial", 0))
        / "files"
    )
    return files.exists() and any(files.rglob("*.py"))


def format_audit_report(
    sampled_trials: list[dict[str, Any]],
    audit_verdicts: list[dict[str, Any]],
    kappa: float,
    matrix: dict[str, int],
) -> str:
    """Format human audit markdown report per docs/07 section 9."""
    lines = [
        "# Human Grader Audit Report",
        "",
        "## 1. Summary of Agreement",
        "",
        f"- **Total Sampled Trials**: {len(sampled_trials)}",
        f"- **Cohen's Kappa (κ)**: {kappa:.4f}",
        "",
        "### 2x2 Contingency Matrix",
        "",
        "| | Human PASS (Correct) | Human FAIL (Incorrect) | Total |",
        "|---|:---:|:---:|:---:|",
        f"| **Grader PASS** | {matrix['TP']} (TP) | {matrix['FP']} (FP) "
        f"| {matrix['TP'] + matrix['FP']} |",
        f"| **Grader FAIL** | {matrix['FN']} (FN) | {matrix['TN']} (TN) "
        f"| {matrix['FN'] + matrix['TN']} |",
        f"| **Total** | {matrix['TP'] + matrix['FN']} | {matrix['FP'] + matrix['TN']} "
        f"| {len(sampled_trials)} |",
        "",
        "## 2. Disagreements and Diagnostics",
        "",
    ]

    disagreements = [
        v for v in audit_verdicts if v["grader_verdict"] != v["human_verdict"]
    ]
    if not disagreements:
        lines.append(
            "Zero disagreements detected. Grader verdicts fully align with human expert review."
        )
    else:
        for idx, d in enumerate(disagreements, 1):
            g_str = "PASS" if d["grader_verdict"] else "FAIL"
            h_str = "PASS" if d["human_verdict"] else "FAIL"
            lines.append(
                f"### Disagreement {idx}: Task `{d['task_id']}` "
                f"(Model: {d['model']}, Trial: {d['trial']})"
            )
            lines.append(f"- **Grader Verdict**: {g_str}")
            lines.append(f"- **Human Verdict**: {h_str}")
            lines.append(f"- **Author Reason**: {d['human_reason']}")
            lines.append("")

    lines.append("")
    lines.append("## 3. Audited Trials Detail")
    lines.append("")
    lines.append("| Trial # | Task ID | Model | Grader Verdict | Human Verdict | Author Reason |")
    lines.append("|:---:|---|---|:---:|:---:|---|")
    for idx, v in enumerate(audit_verdicts, 1):
        g_str = "PASS" if v["grader_verdict"] else "FAIL"
        h_str = "PASS" if v["human_verdict"] else "FAIL"
        reason = v["human_reason"].replace("|", "/")
        lines.append(
            f"| {idx} | `{v['task_id']}` | `{v['model']}` | {g_str} | {h_str} | {reason} |"
        )

    lines.append("")
    return "\n".join(lines)


def _export_sheet(
    sampled: list[dict[str, Any]], raw_dir: Path, sheet_path: Path, key_path: Path
) -> bool:
    """Write the blinded reading sheet and the key file (sampled order)."""
    lines = [
        "# Human audit sheet (blinded)",
        "",
        "For each trial decide: does this code correctly implement the task's rules? Judge it",
        "against the task's `instruction.md` only. You do not see the grader's verdict or the",
        "model name. Record verdicts in a JSON file like:",
        "",
        '    {"T01": {"verdict": true, "reason": "matches R-M1..R-M5"},',
        '     "T02": {"verdict": false, "reason": "keeps last crossing order, not best"}}',
        "",
        "`true` = the code is correct, `false` = it has at least one rule violation.",
        "",
    ]
    keys = []
    for i, t in enumerate(sampled, 1):
        model, task_id, trial = t.get("model", ""), t.get("task_id", ""), t.get("trial", 0)
        keys.append(f"{model}:{task_id}:{trial}")
        code = load_candidate_code(raw_dir, model, task_id, trial)
        lines += [
            "---", "", f"## T{i:02d}: task `{task_id}`",
            f"Rules: `tasks/{task_id}/instruction.md`", "",
            "```python", code, "```", "",
        ]
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet_path.write_text("\n".join(lines), encoding="utf-8")
    key_path.write_text(json.dumps(keys, indent=1), encoding="utf-8")
    print(f"Wrote {len(sampled)} blinded trials to {sheet_path}")
    print(f"Key file (do not open before you finish): {key_path}")
    return True


def run_audit(
    trials_path: Path,
    raw_dir: Path,
    out_path: Path,
    seed: int = 42,
    n_pass: int = 10,
    n_fail: int = 10,
    verdicts_json: Optional[Path] = None,
    auto_agree: bool = False,
    export_sheet: Optional[Path] = None,
    max_chars: int = 6000,
    exclude_prefixes: tuple[str, ...] = ("f9_",),
    force: bool = False,
) -> bool:
    """Execute human audit session.

    With export_sheet, write a blinded reading sheet (anonymous ids T01, T02, ..., full code,
    no grader outcome, no model name) plus a key file with the sampled order, then stop.
    Verdicts can then be given in a JSON file keyed by those ids and passed with verdicts_json.
    """
    if not trials_path.exists():
        print(f"ERROR: Trials file not found at {trials_path}")
        return False

    raw_lines = [
        line.strip()
        for line in trials_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    trials = [json.loads(line) for line in raw_lines]

    key_path = out_path.with_name("audit_key.json")
    if export_sheet is None and key_path.exists():
        # Score exactly the trials that were exported, even if trials.jsonl has grown since.
        order = json.loads(key_path.read_text(encoding="utf-8"))
        by_key = {f"{t['model']}:{t['task_id']}:{t.get('trial', 0)}": t for t in trials}
        sampled = [by_key[k] for k in order if k in by_key]
    else:
        pool = [
            t
            for t in trials
            if not any(t.get("task_id", "").startswith(x) for x in exclude_prefixes if x)
            and is_judgeable(t, raw_dir)
        ]
        print(
            f"Sampling pool: {len(pool)} of {len(trials)} trials "
            f"(excluded: trials with no code to read, tasks starting with {exclude_prefixes})"
        )
        sampled = sample_trials(pool, n_pass=n_pass, n_fail=n_fail, seed=seed)
    if not sampled:
        print("ERROR: No trials available to sample.")
        return False

    if export_sheet is not None:
        if key_path.exists() and not force:
            print(
                f"ERROR: {key_path} already exists. The sample is drawn once; re-drawing after "
                "seeing results defeats the blinding. Pass --force only to start over on purpose."
            )
            return False
        return _export_sheet(sampled, raw_dir, export_sheet, key_path)

    print(
        f"Sampled {len(sampled)} trials with seed {seed} for human review."
    )

    predefined_verdicts: dict[str, dict[str, Any]] = {}
    if verdicts_json and verdicts_json.exists():
        predefined_verdicts = json.loads(verdicts_json.read_text(encoding="utf-8"))

    audit_records = []
    grader_verdicts = []
    human_verdicts = []

    for i, t in enumerate(sampled, 1):
        task_id = t.get("task_id", "unknown")
        model = t.get("model", "unknown")
        trial_num = t.get("trial", 0)
        grader_pass = bool(t.get("passed", False))
        key = f"{model}:{task_id}:{trial_num}"

        print("=" * 80)
        print(f"TRIAL [{i}/{len(sampled)}] Task: {task_id} | Model: {model} (Trial {trial_num})")
        print("=" * 80)

        code_text = load_candidate_code(raw_dir, model, task_id, trial_num)
        print(code_text[:max_chars])
        if len(code_text) > max_chars:
            print("... (truncated; use --export-sheet to read the full code) ...")
        print("-" * 80)

        h_pass: bool
        h_reason: str

        aid = f"T{i:02d}"
        if key in predefined_verdicts or aid in predefined_verdicts:
            v = predefined_verdicts.get(aid) or predefined_verdicts[key]
            h_pass = bool(v.get("verdict", False))
            h_reason = str(v.get("reason", "predefined"))
            v_str = "correct" if h_pass else "incorrect"
            print(f"[Auto-filled] Verdict: {v_str}, Reason: {h_reason}")
        elif auto_agree:
            h_pass = grader_pass
            h_reason = "Auto-agreed in automated verification mode"
            print(f"[Auto-agree] Verdict: {'correct' if h_pass else 'incorrect'}")
        else:
            while True:
                choice = (
                    input("Author verdict [c]orrect / [i]ncorrect / [q]uit: ")
                    .strip()
                    .lower()
                )
                if choice in ("c", "correct"):
                    h_pass = True
                    break
                elif choice in ("i", "incorrect"):
                    h_pass = False
                    break
                elif choice in ("q", "quit"):
                    print("Audit aborted by user.")
                    return False
                print("Invalid input. Please enter 'c' for correct or 'i' for incorrect.")

            h_reason = input("Author rationale for verdict: ").strip()
            if not h_reason:
                h_reason = "Author confirmed"

        audit_records.append(
            {
                "task_id": task_id,
                "model": model,
                "trial": trial_num,
                "grader_verdict": grader_pass,
                "human_verdict": h_pass,
                "human_reason": h_reason,
            }
        )
        grader_verdicts.append(grader_pass)
        human_verdicts.append(h_pass)

    kappa, matrix = compute_cohens_kappa(grader_verdicts, human_verdicts)
    report = format_audit_report(sampled, audit_records, kappa, matrix)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print("\n" + "=" * 80)
    print(f"HUMAN AUDIT COMPLETE: Cohen's Kappa κ = {kappa:.4f}")
    print(f"Report written to: {out_path}")
    print("=" * 80)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Human audit for OrderBook-DST trials")
    parser.add_argument(
        "--trials-file",
        type=Path,
        default=REPO_ROOT / "results" / "main" / "trials.jsonl",
        help="Path to trials.jsonl",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=REPO_ROOT / "results" / "main" / "raw",
        help="Path to raw/ results folder",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "results" / "human_audit.md",
        help="Output markdown report path",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sampling",
    )
    parser.add_argument(
        "--pass-count",
        type=int,
        default=10,
        help="Number of passed trials to sample",
    )
    parser.add_argument(
        "--fail-count",
        type=int,
        default=10,
        help="Number of failed trials to sample",
    )
    parser.add_argument(
        "--verdicts-json",
        type=Path,
        default=None,
        help="Optional JSON file with predefined verdicts for non-interactive mode",
    )
    parser.add_argument(
        "--auto-agree",
        action="store_true",
        help="Automatically agree with grader (for testing / CI)",
    )
    parser.add_argument(
        "--export-sheet",
        type=Path,
        nargs="?",
        const=REPO_ROOT / "results" / "audit_sheet.md",
        default=None,
        help="Write a blinded sheet (default results/audit_sheet.md) and the key, then stop",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow --export-sheet to overwrite an existing audit_key.json",
    )
    parser.add_argument(
        "--include-f9",
        action="store_true",
        help="Include the F9 diagnose-and-fix tasks (excluded by default; report them separately)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=6000,
        help="Characters of code shown per trial in interactive mode",
    )
    args = parser.parse_args()

    success = run_audit(
        trials_path=args.trials_file,
        raw_dir=args.raw_dir,
        out_path=args.out,
        seed=args.seed,
        n_pass=args.pass_count,
        n_fail=args.fail_count,
        verdicts_json=args.verdicts_json,
        auto_agree=args.auto_agree,
        export_sheet=args.export_sheet,
        max_chars=args.max_chars,
        exclude_prefixes=() if args.include_f9 else ("f9_",),
        force=args.force,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
