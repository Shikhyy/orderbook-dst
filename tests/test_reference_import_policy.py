"""Every reference solution must satisfy the same import allowlist as a model's
answer, so 'the reference passes the grader' means the grader models face."""
from pathlib import Path

import pytest

from graders.import_policy import check_candidate_ast

REPO = Path(__file__).resolve().parent.parent
FILES = sorted(
    p for d in ("reference", "reference_alt", "reference_alt_v2", "mutants")
    for p in (REPO / d).glob("f*_*/**/*.py")
)


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(REPO)))
def test_candidate_shaped_files_pass_import_policy(path: Path):
    ok, err = check_candidate_ast(path.read_text(encoding="utf-8"), str(path))
    assert ok, err
