"""tools/export_transcripts.py
Export representative transcripts from a real run into transcripts/.

For every model and task it writes:
  - the lowest-scoring failing trial (so every task has at least one failure),
  - the highest-scoring failing trial if it is a near miss (score >= 0.9),
  - one passing trial, if any.
Each transcript holds the model's full raw reply, the grader result, the first
failure, and the labels on every failing hidden seed. The full prompt is linked,
not copied, because it is identical for every trial of a task (see prompt_sha256).

Usage:
  python tools/export_transcripts.py --in results/main [--in results/feedback] --out transcripts
"""
import argparse
import difflib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from harness.report import NEAR_MISS_SCORE, _failure_class, _sorted_tasks, load_trials  # noqa: E402


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _pick(rows: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    fails = sorted((r for r in rows if not r.get("passed")), key=lambda r: r.get("score", 0.0))
    passes = [r for r in rows if r.get("passed")]
    picked: list[tuple[str, dict[str, Any]]] = []
    if fails:
        picked.append(("failure (lowest score)", fails[0]))
        best = fails[-1]
        if best is not fails[0] and best.get("score", 0.0) >= NEAR_MISS_SCORE:
            picked.append(("near miss (highest failing score)", best))
    if passes:
        picked.append(("pass", passes[0]))
    return picked


MAX_DIFF_LINES = 400


def _reference_diff(rec: dict[str, Any], trial_dir: Path) -> str:
    """Unified diff of each extracted candidate file against the reference."""
    files_dir = trial_dir / "files"
    if not files_dir.exists():
        return ""
    chunks: list[str] = []
    for cand in sorted(p for p in files_dir.rglob("*.py") if p.is_file()):
        ref = REPO_ROOT / "reference" / rec["task_id"] / cand.name
        if not ref.exists():
            continue
        diff = list(difflib.unified_diff(
            ref.read_text(encoding="utf-8").splitlines(),
            cand.read_text(encoding="utf-8").splitlines(),
            fromfile=f"reference/{rec['task_id']}/{cand.name}",
            tofile=f"model/{cand.relative_to(files_dir).as_posix()}",
            lineterm="",
        ))
        if len(diff) > MAX_DIFF_LINES:
            diff = diff[:MAX_DIFF_LINES] + [f"... ({len(diff) - MAX_DIFF_LINES} more lines)"]
        if diff:
            chunks.append("\n".join(diff))
    return "\n\n".join(chunks)


def _render(kind: str, rec: dict[str, Any], run_dir: Path) -> str:
    trial_dir = run_dir / "raw" / rec["model"] / rec["task_id"] / str(rec["trial"])
    reply_file = trial_dir / "reply.txt"
    reply = reply_file.read_text(encoding="utf-8") if reply_file.exists() else "(reply.txt missing)"
    labels = Counter(
        lab for f in (rec.get("seed_failures") or []) for lab in f.get("labels", [])
    )
    lines = [
        f"# {rec['model']} · {rec['task_id']} · trial {rec['trial']} — {kind}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Model ID (requested / served) | `{rec.get('model_id')}` / "
        f"`{rec.get('served_model')}` |",
        f"| Settings | `{json.dumps(rec.get('settings'))}` |",
        f"| Mode | {rec.get('mode', 'single_turn')} |",
        f"| Score (T1 / T2 / T3) | {rec.get('score')} ({rec.get('t1')} / {rec.get('t2')} / "
        f"{rec.get('t3')}) |",
        f"| Outcome | {_failure_class(rec)} |",
        f"| Error | {rec.get('error') or '–'} |",
        f"| Tokens in / out | {rec.get('input_tokens')} / {rec.get('output_tokens')} |",
        f"| Latency (s) | {rec.get('latency_s')} |",
        f"| Stop reason | {rec.get('stop_reason', '–')} |",
        f"| Timestamp | {rec.get('timestamp')} |",
        f"| Prompt | [`prompt.txt`](../../{_rel(trial_dir / 'prompt.txt')}) "
        f"(sha256 `{rec.get('prompt_sha256', '')[:16]}…`) |",
        f"| Raw files | [`{_rel(trial_dir)}/`](../../{_rel(trial_dir)}) |",
        "",
    ]
    ff = rec.get("first_failure")
    if ff:
        diff = json.dumps(ff.get("diff", {}), indent=2)
        if len(diff) > 4000:
            diff = diff[:4000] + "\n... (truncated; full diff in score.json)"
        lines += [
            "## First failure (hidden trace)",
            "",
            f"- Seed {ff.get('seed')}, event {ff.get('event_index')}: "
            f"**{ff.get('invariant')}** — {ff.get('plain_name')}",
            f"- Message: `{ff.get('message')}`",
            "",
            "```json",
            diff,
            "```",
            "",
        ]
    if labels:
        lines += [
            "## Labels on all failing hidden seeds",
            "",
            ", ".join(f"{k}×{v}" for k, v in sorted(labels.items()))
            + f" (over {len(rec.get('seed_failures') or [])} failing seeds of 20)",
            "",
        ]
    if rec.get("turns"):
        lines += ["## Feedback-loop turns", "", "| Turn | Score | Passed | First failure |",
                  "|---|---|---|---|"]
        for t in rec["turns"]:
            f = t.get("first_failure") or {}
            lines.append(f"| {t['turn']} | {t.get('score')} | {t.get('passed')} | "
                         f"{f.get('invariant', '–')} {f.get('message', '')} |")
        lines.append("")
    diff_text = _reference_diff(rec, trial_dir)
    if diff_text:
        lines += [
            "## Diff against the reference solution",
            "",
            "Differences are not errors by themselves (many correct solutions differ from the "
            "reference); use this to find the line that breaks the first failure above.",
            "",
            "```diff",
            diff_text,
            "```",
            "",
        ]
    lines += [
        "## Author analysis",
        "",
        "_Write after reading the reply: what the model got wrong and why, or whether "
        "the grader rejected a valid answer._",
        "",
        "## Model reply (verbatim)",
        "",
        "````text",
        reply,
        "````",
        "",
    ]
    return "\n".join(lines)


def export(run_dirs: list[Path], out_dir: Path) -> list[dict[str, Any]]:
    index: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        trials = load_trials(run_dir / "trials.jsonl")
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for t in trials:
            groups[(t["model"], t["task_id"])].append(t)
        mode_tag = "feedback" if any(t.get("mode") == "feedback_loop" for t in trials) else ""
        for model in sorted({m for m, _ in groups}):
            for task in _sorted_tasks([t for m, t in groups if m == model]):
                for kind, rec in _pick(groups[(model, task)]):
                    name = f"{task}_trial_{rec['trial']}{'_' + mode_tag if mode_tag else ''}.md"
                    dest = out_dir / model / name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(_render(kind, rec, run_dir), encoding="utf-8")
                    index.append({"model": model, "task": task, "kind": kind,
                                  "score": rec.get("score"), "outcome": _failure_class(rec),
                                  "path": dest.relative_to(out_dir).as_posix()})
    lines = [
        "# Representative transcripts",
        "",
        "Generated by `tools/export_transcripts.py` from the run directories. "
        "Every task has its lowest-scoring failure per model; near misses and one "
        "pass are added where they exist.",
        "",
        "| Model | Task | Kind | Score | Outcome | Transcript |",
        "|---|---|---|---|---|---|",
    ]
    for e in index:
        lines.append(f"| {e['model']} | `{e['task']}` | {e['kind']} | {e['score']} | "
                     f"{e['outcome']} | [{e['path']}]({e['path']}) |")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--in", dest="ins", action="append", required=True,
                    help="Run directory with trials.jsonl and raw/ (repeatable)")
    ap.add_argument("--out", default=str(REPO_ROOT / "transcripts"))
    args = ap.parse_args()
    idx = export([Path(p) for p in args.ins], Path(args.out))
    print(f"Wrote {len(idx)} transcripts to {args.out}")


if __name__ == "__main__":
    main()
