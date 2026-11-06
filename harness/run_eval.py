"""harness/run_eval.py
Evaluation harness for OrderBook-DST benchmark.
See docs/08_HARNESS_AND_STATS.md sections 1, 6, 7, and 8.
"""

import argparse
import datetime
import json
import os
import shutil
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
from harness.extract import classify_extract_error, extract_files
from harness.freeguard import check_models
from harness.progress import Progress
from harness.prompt import build_prompt_for_task
from harness.ratelimit import ModelUnavailable, RequestTooLarge, wrap_for_model

REPO_ROOT = Path(__file__).resolve().parent.parent

# Approximate pricing per 1M tokens (USD)
# USD per million tokens. Set real prices per model in models.toml with
# price_in_per_mtok / price_out_per_mtok (copy them from the provider's
# pricing page on the day of the run). This fallback only feeds dry-run
# estimates and is reported as "unpriced" in results.
DEFAULT_PRICING = {"in": 0.0, "out": 0.0}


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


def estimate_cost(m: dict[str, Any], in_tok: int, out_tok: int) -> float:
    """Estimate cost from the per-model prices in models.toml (0.0 if unset)."""
    p_in = float(m.get("price_in_per_mtok", DEFAULT_PRICING["in"]))
    p_out = float(m.get("price_out_per_mtok", DEFAULT_PRICING["out"]))
    return (in_tok * p_in + out_tok * p_out) / 1_000_000.0


def prompt_truncation_suspected(system: str, prompt: str, input_tokens: int) -> bool:
    """True when the provider reports far fewer input tokens than the prompt has.

    Local servers with a small context window (for example Ollama's default)
    silently drop the start of a long prompt; the model then fails for a reason
    that has nothing to do with the task. ~4 characters per token is a rough
    estimate, so only a large shortfall is flagged.
    """
    estimate = (len(system) + len(prompt)) / 4
    return 0 < input_tokens < 0.6 * estimate


def prior_spend_usd(trials_file: Path, m: dict[str, Any]) -> float:
    """Estimated spend already recorded for this model (latency x usd_per_second)."""
    rate = float(m.get("usd_per_second", 0.0))
    if not rate or not trials_file.exists():
        return 0.0
    total = 0.0
    for line in trials_file.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("model") == m.get("label"):
            total += float(rec.get("latency_s") or 0.0) * rate
    return total


def tasks_for_model(m: dict[str, Any], task_ids: list[str]) -> list[str]:
    """A [[model]] entry may restrict itself to a subset with tasks = [...]."""
    only = m.get("tasks")
    return [t for t in task_ids if t in only] if only else task_ids


def start_progress(
    models_cfg: list[dict[str, Any]],
    task_ids: list[str],
    out_dir: Path,
    trials_override: Optional[int],
    completed: set[tuple[str, str, int]],
    mode: str,
) -> Progress:
    labels = {m.get("label") for m in models_cfg}
    expected = {
        str(m.get("label")): len(tasks_for_model(m, task_ids))
        * (trials_override if trials_override is not None else m.get("trials", 5))
        for m in models_cfg
    }
    done = len([k for k in completed if k[0] in labels])
    return Progress(out_dir, sum(expected.values()), already_done=done, mode=mode,
                    expected=expected)


def build_settings(m: dict[str, Any]) -> dict[str, Any]:
    """Settings sent to the adapter: [model.settings] plus model_id and base_url."""
    settings = dict(m.get("settings", {}))
    settings["model_id"] = m.get("model_id", "default")
    for key in ("base_url", "api_key_env", "api_key_secret_env"):
        if key in m:
            settings[key] = m[key]
    return settings


def models_meta(models_cfg: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Model configuration recorded in run_meta.json (no secrets live in models.toml)."""
    return [
        {
            "label": m.get("label"),
            "tier": m.get("tier"),
            "adapter": m.get("adapter"),
            "model_id": m.get("model_id"),
            "settings": m.get("settings", {}),
            "price_in_per_mtok": m.get("price_in_per_mtok"),
            "price_out_per_mtok": m.get("price_out_per_mtok"),
        }
        for m in models_cfg
    ]


def run_dry_run(
    models_cfg: list[dict[str, Any]],
    task_ids: list[str],
    trials_override: Optional[int],
) -> None:
    check_models(models_cfg)
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
        num_trials = trials_override if trials_override is not None else m.get("trials", 5)

        for tid in tasks_for_model(m, task_ids):
            bp = build_prompt_for_task(tid)
            in_tok = len(bp.user_prompt) // 4 + len(bp.system) // 4
            out_tok = 1200  # typical code implementation size
            cost = estimate_cost(m, in_tok, out_tok) * num_trials

            total_calls += num_trials
            total_cost += cost
            row = f"{label:<15} {tid:<15} {num_trials:<8} {in_tok:<12} {out_tok:<12} ${cost:<11.4f}"
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

        # Single-turn trials: re-extract from the saved reply, so an extractor
        # fix applies to replies already paid for (no new API calls).
        reply_file = trial_dir / "reply.txt"
        if record.get("mode", "single_turn") == "single_turn" and reply_file.exists():
            task_meta = tomli.loads(
                (REPO_ROOT / "tasks" / task_id / "task.toml").read_text(encoding="utf-8")
            )
            files, extract_err = extract_files(
                reply_file.read_text(encoding="utf-8"), task_meta.get("target_files", [])
            )
            extract_err = classify_extract_error(extract_err, record.get("stop_reason"))
            if extract_err:
                record.update(error=extract_err, score=0.0, passed=False,
                              t1=0.0, t2=0.0, t3=0.0, first_failure=None, seed_failures=None)
                updated_records.append(record)
                continue
            shutil.rmtree(files_dir, ignore_errors=True)
            _save_candidate_files(files_dir, files)

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
        record["seed_failures"] = new_score.seed_failures
        record["error"] = new_score.error

        (trial_dir / "score.json").write_text(new_score.to_json(), encoding="utf-8")
        updated_records.append(record)

    # A run may have appended records while this regrade was working (a regrade takes minutes).
    # Re-read the file and keep every record that was not in the first read, so that they are
    # not overwritten. Their scores are not regraded: run the regrade again for those.
    seen = {(r["model"], r["task_id"], r["trial"]) for r in updated_records}
    appended = 0
    for line in trials_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if (rec["model"], rec["task_id"], rec["trial"]) not in seen:
            updated_records.append(rec)
            appended += 1
    content = "\n".join(json.dumps(r) for r in updated_records) + "\n"
    trials_file.write_text(content, encoding="utf-8")
    print(f"Regraded {len(updated_records) - appended} trials successfully.")
    if appended:
        print(f"Kept {appended} record(s) appended during the regrade (not regraded).")


def run_single_turn_eval(
    models_cfg: list[dict[str, Any]],
    task_ids: list[str],
    out_dir: Path,
    trials_override: Optional[int],
) -> None:
    check_models(models_cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    trials_file = out_dir / "trials.jsonl"

    # Write run_meta.json
    meta = {
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": get_git_sha(),
        "harness_version": "1.0",
        "python_version": sys.version,
        "trials_override": trials_override,
        "tasks": task_ids,
        "models": models_meta(models_cfg),
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

    progress = start_progress(
        models_cfg, task_ids, out_dir, trials_override, completed, "single_turn"
    )
    for m in models_cfg:
        label = m.get("label", "unknown")
        adapter_type = m.get("adapter", "mock")
        model_id = m.get("model_id", "default")
        settings = build_settings(m)
        num_trials = trials_override if trials_override is not None else m.get("trials", 5)

        adapter = wrap_for_model(
            get_adapter(adapter_type), m, spent_usd=prior_spend_usd(trials_file, m)
        )
        adapter.notify = progress.set_state

        try:
            for tid in tasks_for_model(m, task_ids):
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

                    progress.start_trial(label, tid, trial_idx, num_trials)

                    # Invoke model adapter
                    try:
                        reply = adapter.generate(bp.system, bp.user_prompt, settings)
                    except RequestTooLarge as exc:
                        progress.skip_trial(
                            label, tid, str(exc)[:160], count=num_trials - trial_idx
                        )
                        break  # same prompt every trial: move on to the next task
                    truncated = prompt_truncation_suspected(
                        bp.system, bp.user_prompt, reply.input_tokens
                    )
                    if truncated:
                        print(f"  WARNING: provider reported {reply.input_tokens} input tokens; "
                              "the prompt was probably truncated (context window too small)")
                    (trial_dir / "reply.txt").write_text(reply.text, encoding="utf-8")

                    # Extract files
                    files, extract_err = extract_files(reply.text, expected_targets)
                    extract_err = classify_extract_error(
                        extract_err,
                        reply.raw_meta.get("finish_reason") or reply.raw_meta.get("stop_reason"),
                    )

                    # Save extracted files
                    _save_candidate_files(trial_dir / "files", files)

                    cost_est = estimate_cost(m, reply.input_tokens, reply.output_tokens)

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
                        "tier": m.get("tier"),
                        "task_id": tid,
                        "trial": trial_idx,
                        "mode": "single_turn",
                        "served_model": reply.raw_meta.get("model"),
                        "stop_reason": reply.raw_meta.get("stop_reason")
                        or reply.raw_meta.get("finish_reason"),
                        "empty_reply_retries": reply.raw_meta.get("empty_retries", 0),
                        "settings": {k: v for k, v in settings.items() if k != "model_id"},
                        "prompt_sha256": bp.prompt_sha256,
                        "score": score_rec.score,
                        "passed": score_rec.passed,
                        "t1": score_rec.t1,
                        "t2": score_rec.t2,
                        "t3": score_rec.t3,
                        "error": score_rec.error,
                        "first_failure": score_rec.first_failure,
                        "seed_failures": score_rec.seed_failures,
                        "prompt_truncated_suspected": truncated,
                        "input_tokens": reply.input_tokens,
                        "output_tokens": reply.output_tokens,
                        "cost_usd_est": cost_est,
                        "latency_s": reply.latency_s,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }

                    with trials_file.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(record) + "\n")

                    completed.add(trial_key)
                    progress.finish_trial(
                        label,
                        f"{tid} trial {trial_idx + 1}: score {score_rec.score:.2f} "
                        f"{'PASS' if score_rec.passed else 'FAIL'}"
                        f"{' (' + str(score_rec.error)[:60] + ')' if score_rec.error else ''}"
                        f" | model took {reply.latency_s:.0f}s",
                    )
        except ModelUnavailable as exc:
            progress.model_stopped(label, str(exc))
            print("  Completed trials are saved; run the same command again to resume.")
    progress.finish_run()


def _save_candidate_files(dst_dir: Path, files: dict[str, str]) -> None:
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    for fpath, fcontent in files.items():
        fp = dst_dir / fpath
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(fcontent, encoding="utf-8")


def build_feedback_record(score_rec: ScoreRecord) -> dict[str, Any]:
    """Extract strictly permitted feedback data for multi-turn revision:
    - public test output
    - first violation record: [invariant ID, plain name, message]
    NO hidden trace, seed number, or expected reports.
    """
    first_viol = None
    if score_rec.first_failure:
        ff = score_rec.first_failure
        # Strictly [invariant ID, plain name, message]
        first_viol = [
            str(ff.get("invariant", "")),
            str(ff.get("plain_name", "")),
            str(ff.get("message", "")),
        ]

    return {
        "public_test_output": score_rec.public_test_output or "",
        "first_violation": first_viol,
        "error": score_rec.error,
    }


def format_feedback_prompt(feedback_data: dict[str, Any]) -> str:
    """Format feedback text for model revision turn."""
    parts = [
        "Your previous code submission failed verification.",
        "Here is the test feedback on your submission:",
    ]
    pub = feedback_data.get("public_test_output")
    if pub:
        parts.append(f"### Public Unit Test Output:\n```\n{pub.strip()}\n```")

    first_v = feedback_data.get("first_violation")
    if first_v:
        inv_id, name, msg = first_v
        parts.append(
            f"### Invariant Violation:\n- Invariant: {inv_id}\n- Name: {name}\n- Details: {msg}"
        )

    err = feedback_data.get("error")
    if err and not pub and not first_v:
        parts.append(f"### Grader Error:\n{err}")

    parts.append(
        "Please provide your complete revised solution using the standard format:\n"
        "### FILE: <relative_path>\n"
        "```python\n"
        "# your code\n"
        "```"
    )
    return "\n\n".join(parts)


def run_feedback_loop_eval(
    models_cfg: list[dict[str, Any]],
    task_ids: list[str],
    out_dir: Path,
    trials_override: Optional[int],
    max_revisions: int = 3,
) -> None:
    check_models(models_cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = out_dir / "raw"
    trials_file = out_dir / "trials.jsonl"

    meta = {
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": get_git_sha(),
        "harness_version": "1.0",
        "mode": "feedback_loop",
        "max_revisions": max_revisions,
        "python_version": sys.version,
        "trials_override": trials_override,
        "tasks": task_ids,
        "models": models_meta(models_cfg),
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    completed: set[tuple[str, str, int]] = set()
    if trials_file.exists():
        for line in trials_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rec = json.loads(line)
                    completed.add((rec["model"], rec["task_id"], rec["trial"]))
                except Exception:
                    continue

    progress = start_progress(
        models_cfg, task_ids, out_dir, trials_override, completed, "feedback_loop"
    )
    for m in models_cfg:
        label = m.get("label", "unknown")
        adapter_type = m.get("adapter", "mock")
        model_id = m.get("model_id", "default")
        settings = build_settings(m)
        num_trials = trials_override if trials_override is not None else m.get("trials", 5)

        adapter = wrap_for_model(
            get_adapter(adapter_type), m, spent_usd=prior_spend_usd(trials_file, m)
        )
        adapter.notify = progress.set_state

        try:
            for tid in tasks_for_model(m, task_ids):
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

                    progress.start_trial(label, tid, trial_idx, num_trials)

                    total_in_tok = 0
                    total_out_tok = 0
                    total_latency = 0.0
                    turns: list[dict[str, Any]] = []

                    # Turn 0: Initial Attempt
                    try:
                        reply = adapter.generate(bp.system, bp.user_prompt, settings)
                    except RequestTooLarge as exc:
                        progress.skip_trial(
                            label, tid, str(exc)[:160], count=num_trials - trial_idx
                        )
                        break  # same prompt every trial: move on to the next task
                    truncated = prompt_truncation_suspected(
                        bp.system, bp.user_prompt, reply.input_tokens
                    )
                    if truncated:
                        print(f"  WARNING: provider reported {reply.input_tokens} input tokens; "
                              "the prompt was probably truncated (context window too small)")
                    (trial_dir / "reply_turn_0.txt").write_text(reply.text, encoding="utf-8")
                    (trial_dir / "reply.txt").write_text(reply.text, encoding="utf-8")
                    total_in_tok += reply.input_tokens
                    total_out_tok += reply.output_tokens
                    total_latency += reply.latency_s

                    files, extract_err = extract_files(reply.text, expected_targets)
                    extract_err = classify_extract_error(
                        extract_err,
                        reply.raw_meta.get("finish_reason") or reply.raw_meta.get("stop_reason"),
                    )
                    _save_candidate_files(trial_dir / "files_turn_0", files)
                    _save_candidate_files(trial_dir / "files", files)

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

                    (trial_dir / "score_turn_0.json").write_text(
                        score_rec.to_json(), encoding="utf-8"
                    )

                    turn_record = {
                        "turn": 0,
                        "score": score_rec.score,
                        "passed": score_rec.passed,
                        "t1": score_rec.t1,
                        "t2": score_rec.t2,
                        "t3": score_rec.t3,
                        "error": score_rec.error,
                        "first_failure": score_rec.first_failure,
                        "in_tok": reply.input_tokens,
                        "out_tok": reply.output_tokens,
                    }
                    turns.append(turn_record)

                    # Revisions: up to max_revisions (1..3)
                    current_reply_text = reply.text
                    for rev_idx in range(1, max_revisions + 1):
                        if score_rec.passed:
                            break

                        feedback_data = build_feedback_record(score_rec)
                        feedback_prompt = format_feedback_prompt(feedback_data)
                        (trial_dir / f"feedback_revision_{rev_idx}.txt").write_text(
                            feedback_prompt, encoding="utf-8"
                        )

                        rev_user_prompt = (
                            f"{bp.user_prompt}\n\n"
                            f"=== PREVIOUS SUBMISSION ===\n{current_reply_text}\n\n"
                            f"=== TEST FEEDBACK ===\n{feedback_prompt}"
                        )

                        rev_reply = adapter.generate(bp.system, rev_user_prompt, settings)
                        (trial_dir / f"reply_revision_{rev_idx}.txt").write_text(
                            rev_reply.text, encoding="utf-8"
                        )
                        (trial_dir / "reply.txt").write_text(rev_reply.text, encoding="utf-8")
                        current_reply_text = rev_reply.text

                        total_in_tok += rev_reply.input_tokens
                        total_out_tok += rev_reply.output_tokens
                        total_latency += rev_reply.latency_s

                        files, extract_err = extract_files(rev_reply.text, expected_targets)
                        _save_candidate_files(trial_dir / f"files_revision_{rev_idx}", files)
                        _save_candidate_files(trial_dir / "files", files)

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

                        (trial_dir / f"score_revision_{rev_idx}.json").write_text(
                            score_rec.to_json(), encoding="utf-8"
                        )

                        turn_record = {
                            "turn": rev_idx,
                            "score": score_rec.score,
                            "passed": score_rec.passed,
                            "t1": score_rec.t1,
                            "t2": score_rec.t2,
                            "t3": score_rec.t3,
                            "error": score_rec.error,
                            "first_failure": score_rec.first_failure,
                            "in_tok": rev_reply.input_tokens,
                            "out_tok": rev_reply.output_tokens,
                        }
                        turns.append(turn_record)

                    # Final scores and metadata
                    (trial_dir / "score.json").write_text(score_rec.to_json(), encoding="utf-8")
                    (trial_dir / "turns.json").write_text(
                        json.dumps(turns, indent=2), encoding="utf-8"
                    )

                    cost_est = estimate_cost(m, total_in_tok, total_out_tok)
                    record = {
                        "model": label,
                        "model_id": model_id,
                        "tier": m.get("tier"),
                        "task_id": tid,
                        "trial": trial_idx,
                        "mode": "feedback_loop",
                        "settings": {k: v for k, v in settings.items() if k != "model_id"},
                        "prompt_sha256": bp.prompt_sha256,
                        "score": score_rec.score,
                        "passed": score_rec.passed,
                        "t1": score_rec.t1,
                        "t2": score_rec.t2,
                        "t3": score_rec.t3,
                        "error": score_rec.error,
                        "first_failure": score_rec.first_failure,
                        "seed_failures": score_rec.seed_failures,
                        "num_revisions": len(turns) - 1,
                        "turns": turns,
                        "prompt_truncated_suspected": truncated,
                        "input_tokens": total_in_tok,
                        "output_tokens": total_out_tok,
                        "cost_usd_est": cost_est,
                        "latency_s": total_latency,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }

                    with trials_file.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(record) + "\n")

                    completed.add(trial_key)
                    progress.finish_trial(
                        label,
                        f"{tid} trial {trial_idx + 1}: score {score_rec.score:.2f} "
                        f"{'PASS' if score_rec.passed else 'FAIL'} after {len(turns) - 1} "
                        f"revision(s)"
                        f"{' (' + str(score_rec.error)[:60] + ')' if score_rec.error else ''}",
                    )
        except ModelUnavailable as exc:
            progress.model_stopped(label, str(exc))
            print("  Completed trials are saved; run the same command again to resume.")
    progress.finish_run()


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
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated model labels to run (default: all in the file)")
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
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        models_cfg = [m for m in models_cfg if m.get("label") in wanted]
        missing = wanted - {m.get("label") for m in models_cfg}
        if missing:
            parser.error(f"--only: no model labelled {sorted(missing)} in {models_path}")

    if args.dry_run:
        run_dry_run(models_cfg, task_ids, args.trials)
        return

    if args.mode == "single_turn":
        run_single_turn_eval(models_cfg, task_ids, Path(args.out), args.trials)
    elif args.mode == "feedback_loop":
        run_feedback_loop_eval(models_cfg, task_ids, Path(args.out), args.trials)


if __name__ == "__main__":
    main()
