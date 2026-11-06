"""Two guards added with the Nov 6 grader fixes.

1. A checkpoint with "exact_reports": true fails when an extra report appears; the default
   still allows extra reports. The F8 checkpoint "chk_zero_share_is_not_reported" uses it.
2. `run_regrade` keeps a record that a run appended while the regrade was working.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import harness.run_eval as re
from graders.dst_grader import grade_task

BANKRUPTCY = "exchange_core/handlers/bankruptcy.py"


def _grade_f8(path: str):
    return grade_task("f8_adl_b", {BANKRUPTCY: Path(path).read_text()}, is_candidate=True)


def test_exact_reports_checkpoint_catches_a_zero_share_report():
    trace = json.loads(Path("tasks/f8_adl_b/tier2_trace.json").read_text())
    exact = {c["name"]: c.get("exact_reports", False) for c in trace["checkpoints"]}
    assert exact["chk_zero_share_is_not_reported"] is True
    assert sum(exact.values()) == 1  # only the checkpoint that needs it

    ref = _grade_f8("reference/f8_adl_b/bankruptcy.py")
    assert ref.t2 == 1.0
    mutant = _grade_f8("mutants/f8_adl_b/m_zero_share_reported/bankruptcy.py")
    assert mutant.t2 < 1.0 and not mutant.passed


def test_new_checkpoints_catch_the_three_boundary_mutants():
    for task, rel, mutant in [
        ("f8_adl_b", BANKRUPTCY, "mutants/f8_adl_b/m_vault_not_floored/bankruptcy.py"),
        ("f7_funding_b", "exchange_core/handlers/funding.py",
         "mutants/f7_funding_b/m_vault_floor_zero/funding.py"),
        ("f4_waterfall_b", "exchange_core/handlers/shock.py",
         "mutants/f4_waterfall_b/m_retest_strict_inequality/shock.py"),
    ]:
        rec = grade_task(task, {rel: Path(mutant).read_text()}, is_candidate=True)
        assert rec.t1 == 1.0 and rec.t2 < 1.0 and not rec.passed, (task, rec.t1, rec.t2)


def test_regrade_keeps_a_record_appended_during_the_regrade(tmp_path, monkeypatch):
    def record(trial):
        return {"model": "m", "task_id": "f1_fee_a", "trial": trial, "mode": "single_turn",
                "score": 0.0, "passed": False, "t1": 0.0, "t2": 0.0, "t3": 0.0,
                "first_failure": None, "seed_failures": None, "error": None}

    trials = tmp_path / "trials.jsonl"
    trials.write_text(json.dumps(record(0)) + "\n")
    files = tmp_path / "raw" / "m" / "f1_fee_a" / "0" / "files"
    files.mkdir(parents=True)
    (files / "x.py").write_text("pass\n")

    def fake_grade(task_id, files, is_candidate):
        # a run appends trial 1 while the regrade is grading trial 0
        with trials.open("a") as f:
            f.write(json.dumps(record(1)) + "\n")
        return SimpleNamespace(score=1.0, passed=True, t1=1.0, t2=1.0, t3=1.0,
                               first_failure=None, seed_failures=None, error=None,
                               to_json=lambda: "{}")

    monkeypatch.setattr(re, "grade_task", fake_grade)
    re.run_regrade(tmp_path)

    kept = [json.loads(line) for line in trials.read_text().splitlines()]
    assert [r["trial"] for r in kept] == [0, 1]
    assert kept[0]["passed"] is True      # regraded
    assert kept[1]["passed"] is False     # appended record kept, untouched
