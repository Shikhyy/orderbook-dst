"""Grader diagnostic labels: every failing hidden seed records all labels seen at
its first failing event, and these labels never change the score."""
from pathlib import Path

from graders.dst_grader import grade_task

REPO = Path(__file__).resolve().parent.parent


def _load(task: str, rel_target: str, src: Path) -> dict[str, str]:
    return {rel_target: src.read_text(encoding="utf-8")}


def test_reference_has_no_seed_failures():
    files = _load(
        "f1_fee_b",
        "exchange_core/handlers/settle.py",
        REPO / "reference" / "f1_fee_b" / "settle.py",
    )
    rec = grade_task("f1_fee_b", files)
    assert rec.passed
    assert rec.seed_failures == []


def test_vault_mutant_is_labelled_as_cash_conservation_breach():
    files = _load(
        "f1_fee_b",
        "exchange_core/handlers/settle.py",
        REPO / "mutants" / "f1_fee_b" / "m_rebate_not_paid_from_vault" / "settle.py",
    )
    rec = grade_task("f1_fee_b", files)
    assert not rec.passed
    assert rec.seed_failures
    failing = round((1.0 - rec.t3) * 20)
    assert len(rec.seed_failures) == failing
    assert any("I1" in f["labels"] for f in rec.seed_failures)
