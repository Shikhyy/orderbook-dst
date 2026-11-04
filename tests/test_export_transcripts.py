"""Transcript export: every task gets its lowest-scoring failure, plus a near
miss and a pass where they exist, with the verbatim reply."""
import json
from pathlib import Path

from tools.export_transcripts import export


def _trial(run: Path, model: str, task: str, trial: int, score: float, passed: bool) -> dict:
    d = run / "raw" / model / task / str(trial)
    d.mkdir(parents=True)
    (d / "reply.txt").write_text(f"REPLY {task} {trial}", encoding="utf-8")
    (d / "prompt.txt").write_text("PROMPT", encoding="utf-8")
    return {"model": model, "task_id": task, "trial": trial, "score": score,
            "passed": passed, "t1": 1.0, "t2": 1.0, "t3": score,
            "first_failure": None if passed else {"invariant": "I1", "seed": 1,
                                                  "event_index": 2, "plain_name": "x",
                                                  "message": "m", "diff": {}},
            "seed_failures": [] if passed else [{"seed": 1, "event_index": 2,
                                                 "labels": ["D1", "I1"]}]}


def test_export_picks_failure_near_miss_and_pass(tmp_path: Path):
    run = tmp_path / "main"
    rows = [
        _trial(run, "m", "f1_fee_b", 0, 0.3, False),
        _trial(run, "m", "f1_fee_b", 1, 0.95, False),
        _trial(run, "m", "f1_fee_b", 2, 1.0, True),
        _trial(run, "m", "f2_replace_a", 0, 1.0, True),
    ]
    (run / "trials.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    out = tmp_path / "transcripts"
    idx = export([run], out)
    kinds = sorted((e["task"], e["kind"]) for e in idx)
    assert kinds == [
        ("f1_fee_b", "failure (lowest score)"),
        ("f1_fee_b", "near miss (highest failing score)"),
        ("f1_fee_b", "pass"),
        ("f2_replace_a", "pass"),
    ]
    text = (out / "m" / "f1_fee_b_trial_0.md").read_text()
    assert "REPLY f1_fee_b 0" in text and "I1×1" in text
    assert (out / "README.md").exists()
