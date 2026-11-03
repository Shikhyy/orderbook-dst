"""harness/run_eval.py
Evaluation harness for OrderBook-DST benchmark.
See docs/08_HARNESS_AND_STATS.md sections 1, 6, 7, and 8.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore

from graders.dst_grader import ScoreRecord, grade_task
from harness.adapters import (
    AnthropicAdapter,
    MockAdapter,
    ModelAdapter,
    OpenAIAdapter,
    OpenAICompatAdapter,
)
from harness.extract import extract_files
from harness.prompt import build_prompt_for_task

REPO_ROOT = Path(__file__).resolve().parent.parent

# Approximate pricing per 1M tokens (USD)
MODEL_PRICING = {
    "claude-3-7-sonnet": {"in": 3.0, "out": 15.0},
    "gpt-4o": {"in": 2.5, "out": 10.0},
    "default": {"in": 0.5, "out": 1.5},
}


def get_git_sha() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def get_adapter(adapter_name: str) -> ModelAdapter:
    if adapter_name == "anthropic":
        return AnthropicAdapter()
    elif adapter_name == "openai":
        return OpenAIAdapter()
    elif adapter_name == "openai_compat":
        return OpenAICompatAdapter()
    elif adapter_name == "mock":
        return MockAdapter()
    else:
        raise ValueError(f"Unknown adapter: {adapter_name}")


def estimate_cost(model_id: str, in_tok: int, out_tok: int) -> float:
    rates = MODEL_PRICING.get("default", {"in": 0.5, "out": 1.5})
    for k, r in MODEL_PRICING.items():
        if k in model_id.lower():
            rates = r
            break
    return (in_tok * rates["in"] + out_tok * rates["out"]) / 1_000_000.0


def run_dry_run(
    models_cfg: list[dict[str, Any]],
    task_ids: list[str],
    trials_override: Optional[int],
) -> None:
    print("=" * 80)
    print("ORDERBOOK-DST EVALUATION -- DRY RUN")
    print("=" * 80)
    total_calls = 0
    total_cost = 0.0

    header = (
        f"{'Model':<15} {'Task':<15} {'Trials':<8} "
        f"{'Est In Tok':<12} {'Est Out Tok':<12} {'Est Cost ($)':<12}"
    )
    print(header)
    print("-" * 80)

    for m in models_cfg:
        label = m.get("label", "unknown")
        model_id = m.get("model_id", "default")
        num_trials = trials_override if trials_override is not None else m.get("trials", 5)

        for tid in task_ids:
            bp = build_prompt_for_task(tid)
            in_tok = len(bp.user_prompt) // 4 + len(bp.system) // 4
            out_tok = 1200  # typical code implementation size
            cost = estimate_cost(model_id, in_tok, out_tok) * num_trials

            total_calls += num_trials
            total_cost += cost
            row = (
                f"{label:<15} {tid:<15} {num_trials:<8} "
                f"{in_tok:<12} {out_tok:<12} ${cost:<11.4f}"
            )
            print(row)

    print("-" * 80)
    print(f"Total API Calls:     {total_calls}")
    print(f"Total Estimated Cost: ${total_cost:.4f}")
    print("=" * 80)


def run_regrade(out_dir: Path) -> None:
    trials_file = out_dir / "trials.jsonl"
    if not trials_file.exists():
        print(f"No trials.jsonl found in {out_dir}")
        return

    print(f"Regrading all trials in {out_dir}...")
    raw_lines = trials_file.read_text(encoding="utf-8").splitlines()
    lines = [line.strip() for line in raw_lines if line.strip()]
    updated_records = []

    for line in lines:
        record = json.loads(line)
        model = record["model"]
        task_id = record["task_id"]
        trial = record["trial"]

        trial_dir = out_dir / "raw" / model / task_id / str(trial)
        files_dir = trial_dir / "files"
        if not files_dir.exists():
            updated_records.append(record)
            continue

        # Load candidate files
        cand_files: dict[str, str] = {}
        for root, _, filenames in os.walk(files_dir):
            for fn in filenames:
                fp = Path(root) / fn
                rel = fp.relative_to(files_dir).as_posix()
                cand_files[rel] = fp.read_text(encoding="utf-8")

        new_score = grade_task(task_id, cand_files, is_candidate=True)
        record["score"] = new_score.score
        record["passed"] = new_score.passed
        record["t1"] = new_score.t1
        record["t2"] = new_score.t2
        record["t3"] = new_score.t3
        record["first_failure"] = new_score.first_failure

        (trial_dir / "score.json").write_text(new_score.to_json(), encoding="utf-8")
        updated_records.append(record)

    content = "\n".join(json.dumps(r) for r in updated_records) + "\n"
    trials_file.write_text(content, encoding="utf-8")
    print(f"Regraded {len(updated_records)} trials successfully.")


def run_single_turn_eval(
    models_cfg: list[dict[str, Any]],
    task_ids: list[str],
    out_dir: Path,
    trials_override: Optional[int],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    trials_file = out_dir / "trials.jsonl"

    # Write run_meta.json
    meta = {
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": get_git_sha(),
        "harness_version": "1.0",
        "python_version": sys.version,
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Read existing completed trials to support resume
    completed: set[tuple[str, str, int]] = set()
    if trials_file.exists():
        for line in trials_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    completed.add((rec["model"], rec["task_id"], rec["trial"]))
                except Exception:
                    continue

    for m in models_cfg:
        label = m.get("label", "unknown")
        adapter_type = m.get("adapter", "mock")
        model_id = m.get("model_id", "default")
        settings = m.get("settings", {})
        settings["model_id"] = model_id
        num_trials = trials_override if trials_override is not None else m.get("trials", 5)

        adapter = get_adapter(adapter_type)

        for tid in task_ids:
            task_toml = REPO_ROOT / "tasks" / tid / "task.toml"
            task_meta = tomli.loads(task_toml.read_text(encoding="utf-8"))
            expected_targets = task_meta.get("target_files", [])

            bp = build_prompt_for_task(tid)

            for trial_idx in range(num_trials):
                trial_key = (label, tid, trial_idx)
                trial_dir = raw_dir / label / tid / str(trial_idx)
                if trial_key in completed and (trial_dir / "score.json").exists():
                    print(f"Skipping completed trial: {label} / {tid} / trial {trial_idx}")
                    continue

                trial_dir.mkdir(parents=True, exist_ok=True)
                (trial_dir / "prompt.txt").write_text(bp.user_prompt, encoding="utf-8")

                print(f"Running: {label} | Task: {tid} | Trial: {trial_idx + 1}/{num_trials}...")

                # Invoke model adapter
                reply = adapter.generate(bp.system, bp.user_prompt, settings)
                (trial_dir / "reply.txt").write_text(reply.text, encoding="utf-8")

                # Extract files
                files, extract_err = extract_files(reply.text, expected_targets)

                # Save extracted files
                files_dir = trial_dir / "files"
                if files_dir.exists():
                    import shutil
                    shutil.rmtree(files_dir)
                files_dir.mkdir(parents=True, exist_ok=True)
                for fpath, fcontent in files.items():
                    fp = files_dir / fpath
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_text(fcontent, encoding="utf-8")

                cost_est = estimate_cost(model_id, reply.input_tokens, reply.output_tokens)

                if extract_err:
                    score_rec = ScoreRecord(
                        task_id=tid,
                        t1=0.0,
                        t2=0.0,
                        t3=0.0,
                        score=0.0,
                        passed=False,
                        error=extract_err,
                    )
                else:
                    score_rec = grade_task(tid, files, is_candidate=True)

                (trial_dir / "score.json").write_text(score_rec.to_json(), encoding="utf-8")

                record = {
                    "model": label,
                    "model_id": model_id,
                    "task_id": tid,
                    "trial": trial_idx,
                    "mode": "single_turn",
                    "prompt_sha256": bp.prompt_sha256,
                    "score": score_rec.score,
                    "passed": score_rec.passed,
                    "t1": score_rec.t1,
                    "t2": score_rec.t2,
                    "t3": score_rec.t3,
                    "error": score_rec.error,
                    "first_failure": score_rec.first_failure,
                    "input_tokens": reply.input_tokens,
                    "output_tokens": reply.output_tokens,
                    "cost_usd_est": cost_est,
                    "latency_s": reply.latency_s,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }

                with trials_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")

                completed.add(trial_key)
                msg = (
                    f"  Finished: score={score_rec.score:.2f}, "
                    f"passed={score_rec.passed}, err={score_rec.error}"
                )
                print(msg)


def main() -> None:
    parser = argparse.ArgumentParser(description="OrderBook-DST Evaluation Harness")
    parser.add_argument(
        "--models", type=str, default="models.example.toml", help="Path to models.toml"
    )
    parser.add_argument(
        "--mode", type=str, default="single_turn", choices=["single_turn", "feedback_loop"]
    )
    parser.add_argument("--trials", type=int, default=None, help="Override number of trials")
    parser.add_argument("--out", type=str, default="results/main", help="Output directory")
    parser.add_argument("--tasks", type=str, default=None, help="Comma-separated task IDs")
    parser.add_argument("--dry-run", action="store_true", help="Print call estimates and cost")
    parser.add_argument("--regrade", type=str, default=None, help="Regrade existing result folder")

    args = parser.parse_args()

    if args.regrade:
        run_regrade(Path(args.regrade))
        return

    # Load tasks
    if args.tasks:
        task_ids = [t.strip() for t in args.tasks.split(",") if t.strip()]
    else:
        tasks_dir = REPO_ROOT / "tasks"
        task_ids = sorted(
            [d.name for d in tasks_dir.iterdir() if d.is_dir() and (d / "task.toml").exists()]
        )

    models_path = Path(args.models)
    if not models_path.exists():
        models_path = REPO_ROOT / "models.example.toml"
    models_data = tomli.loads(models_path.read_text(encoding="utf-8"))
    models_cfg = models_data.get("model", [])

    if args.dry_run:
        run_dry_run(models_cfg, task_ids, args.trials)
        return

    if args.mode == "single_turn":
        run_single_turn_eval(models_cfg, task_ids, Path(args.out), args.trials)
    else:
        raise NotImplementedError("Feedback loop mode is scheduled for milestone M8 ablation")


if __name__ == "__main__":
    main()
