"""tests/test_human_audit.py
Unit tests for human audit tool and Cohen's kappa agreement metrics.
"""
import json
from pathlib import Path

from tools.human_audit import (
    compute_cohens_kappa,
    run_audit,
    sample_trials,
)


def test_cohens_kappa_perfect_agreement() -> None:
    """Perfect agreement between grader and human yields kappa = 1.0."""
    grader = [True, True, False, False, True, False]
    human = [True, True, False, False, True, False]
    kappa, matrix = compute_cohens_kappa(grader, human)
    assert kappa == 1.0
    assert matrix["TP"] == 3
    assert matrix["TN"] == 3
    assert matrix["FP"] == 0
    assert matrix["FN"] == 0


def test_cohens_kappa_hand_calculated() -> None:
    """Test Cohen's kappa against hand-calculated values.

    Hand calculation:
    10 trials:
    grader = [True, True, True, True, True, False, False, False, False, False]
    human  = [True, True, True, True, False, False, False, False, False, True]
    TP = 4, FP = 1, TN = 4, FN = 1.
    p_o = (4 + 4) / 10 = 0.80
    p_grader_pass = 5/10 = 0.5, p_grader_fail = 5/10 = 0.5
    p_human_pass = 5/10 = 0.5,  p_human_fail = 5/10 = 0.5
    p_e = 0.5 * 0.5 + 0.5 * 0.5 = 0.50
    kappa = (0.80 - 0.50) / (1.0 - 0.50) = 0.30 / 0.50 = 0.60
    """
    grader = [True, True, True, True, True, False, False, False, False, False]
    human = [True, True, True, True, False, False, False, False, False, True]
    kappa, matrix = compute_cohens_kappa(grader, human)
    assert kappa == 0.6
    assert matrix["TP"] == 4
    assert matrix["TN"] == 4
    assert matrix["FP"] == 1
    assert matrix["FN"] == 1


def test_sample_trials_reproducible() -> None:
    """Sample trials selects exact passed and failed counts deterministically."""
    synthetic_trials = []
    for i in range(25):
        synthetic_trials.append(
            {"model": "m1", "task_id": f"t_{i}", "trial": 1, "passed": True}
        )
    for i in range(25):
        synthetic_trials.append(
            {"model": "m1", "task_id": f"t_{i}", "trial": 2, "passed": False}
        )

    s1 = sample_trials(synthetic_trials, n_pass=10, n_fail=10, seed=123)
    s2 = sample_trials(synthetic_trials, n_pass=10, n_fail=10, seed=123)

    assert len(s1) == 20
    assert s1 == s2
    n_p = sum(1 for t in s1 if t["passed"])
    n_f = sum(1 for t in s1 if not t["passed"])
    assert n_p == 10
    assert n_f == 10


def test_run_audit_end_to_end(tmp_path: Path) -> None:
    """End-to-end audit execution in automated auto_agree mode."""
    trials_file = tmp_path / "trials.jsonl"
    raw_dir = tmp_path / "raw"
    out_md = tmp_path / "human_audit.md"

    # Create dummy trials
    trials = [
        {"model": "m1", "task_id": "f1_fee_a", "trial": 1, "passed": True},
        {"model": "m1", "task_id": "f1_fee_a", "trial": 2, "passed": False},
        {"model": "m1", "task_id": "f2_replace_a", "trial": 1, "passed": True},
        {"model": "m1", "task_id": "f2_replace_a", "trial": 2, "passed": False},
    ]
    with open(trials_file, "w", encoding="utf-8") as f:
        for t in trials:
            f.write(json.dumps(t) + "\n")

    # Create dummy code file
    code_file = raw_dir / "m1" / "f1_fee_a" / "1" / "files" / "fee_rule.py"
    code_file.parent.mkdir(parents=True, exist_ok=True)
    code_file.write_text("# dummy implementation", encoding="utf-8")

    success = run_audit(
        trials_path=trials_file,
        raw_dir=raw_dir,
        out_path=out_md,
        seed=42,
        n_pass=2,
        n_fail=2,
        auto_agree=True,
    )
    assert success is True
    assert out_md.exists()
    content = out_md.read_text(encoding="utf-8")
    assert "Human Grader Audit Report" in content
    assert "**Cohen's Kappa (κ)**: 1.0000" in content
    assert "| **Grader PASS** | 2 (TP) | 0 (FP) | 2 |" in content


def test_export_sheet_is_blind_and_ids_score(tmp_path: Path) -> None:
    """The exported sheet hides model and grader outcome; id-keyed verdicts are scored."""
    raw = tmp_path / "raw"
    trials = []
    for i in range(4):
        d = raw / f"model_{i}" / "taskX" / "0" / "files"
        d.mkdir(parents=True)
        (d / "mod.py").write_text(f"x = {i}\n", encoding="utf-8")
        trials.append({"model": f"model_{i}", "task_id": "taskX", "trial": 0,
                       "passed": i % 2 == 0})
    tf = tmp_path / "trials.jsonl"
    tf.write_text("\n".join(json.dumps(t) for t in trials), encoding="utf-8")
    out = tmp_path / "human_audit.md"
    sheet = tmp_path / "sheet.md"

    assert run_audit(tf, raw, out, n_pass=2, n_fail=2, export_sheet=sheet)
    text = sheet.read_text(encoding="utf-8")
    assert "T01" in text and "T04" in text
    assert "model_" not in text and "passed" not in text.lower()

    verdicts = tmp_path / "v.json"
    verdicts.write_text(
        json.dumps({f"T{i:02d}": {"verdict": True, "reason": "ok"} for i in range(1, 5)}),
        encoding="utf-8",
    )
    assert run_audit(tf, raw, out, n_pass=2, n_fail=2, verdicts_json=verdicts)
    assert "Cohen" in out.read_text(encoding="utf-8")
