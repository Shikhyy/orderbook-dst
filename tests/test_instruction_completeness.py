"""A task is only fair if its prompt states what the grader's reference relies on.

Found during the first real-model run: three coupled tasks never said that the
engine object keeps its config at `engine.cfg` and its state at `engine.state`,
so a model that wrote `engine.config` failed for a reason the prompt never
covered. This test fails if any reference solution reads an `engine.<member>`
that the task instruction does not document.
"""
import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
B_TASKS = [
    "f1_fee_b", "f2_replace_b", "f3_fix_b", "f4_waterfall_b", "f5_basket_b",
    "f6_match_b", "f7_funding_b",
]


def _engine_members(path: Path) -> set[str]:
    members: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "engine"):
            members.add(node.attr)
    return members


@pytest.mark.parametrize("task", B_TASKS)
def test_every_engine_member_used_by_a_reference_is_documented(task: str):
    instruction = (REPO / "tasks" / task / "instruction.md").read_text(encoding="utf-8")
    for ref_dir in ("reference", "reference_alt_v2"):
        for ref in sorted((REPO / ref_dir / task).glob("*.py")):
            for member in sorted(_engine_members(ref)):
                assert f"engine.{member}" in instruction, (
                    f"{ref.relative_to(REPO)} uses engine.{member}, which "
                    f"tasks/{task}/instruction.md does not document"
                )
