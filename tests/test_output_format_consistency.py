"""The output format a model is told to use must be one layout, and the extractor
must accept it. Found in the first real-model run: the system message put
`### FILE:` above the code fence while four instructions put it inside, and the
extractor accepted only the first, so a model that followed the instruction was
scored as a FORMAT_ERROR."""
import tomllib
from pathlib import Path

import pytest

from harness.extract import extract_files
from harness.prompt import SYSTEM_MESSAGE

REPO = Path(__file__).resolve().parent.parent
TASKS = sorted(d.name for d in (REPO / "tasks").iterdir() if (d / "task.toml").exists())


def _targets(task: str) -> list[str]:
    return tomllib.loads((REPO / "tasks" / task / "task.toml").read_text())["target_files"]


def _reference_task(task: str) -> str:
    """A diagnose-and-fix task (F9) has no reference of its own: it is graded as another."""
    meta = tomllib.loads((REPO / "tasks" / task / "task.toml").read_text())
    return str(meta.get("grades_as", task))


@pytest.mark.parametrize("task", TASKS)
def test_instruction_example_uses_the_same_layout_as_the_system_message(task: str):
    lines = (REPO / "tasks" / task / "instruction.md").read_text().splitlines()
    sys_lines = SYSTEM_MESSAGE.splitlines()
    sys_idx = next(i for i, ln in enumerate(sys_lines) if ln.startswith("### FILE:"))
    assert sys_lines[sys_idx + 1].startswith("```"), "system message layout changed"
    for i, ln in enumerate(lines):
        if ln.startswith("### FILE:"):
            assert not lines[i - 1].startswith("```"), (
                f"tasks/{task}/instruction.md line {i + 1}: marker inside the fence, "
                "but the system message puts it above"
            )
            assert lines[i + 1].startswith("```python")


@pytest.mark.parametrize("task", TASKS)
def test_both_layouts_extract_the_reference_solution(task: str):
    target = _targets(task)[0]
    ref_dir = REPO / "reference" / _reference_task(task)
    code = next(ref_dir.glob("*.py")).read_text()
    above = f"### FILE: {target}\n```python\n{code}\n```\n"
    inside = f"```python\n### FILE: {target}\n{code}\n```\n"
    for reply in (above, inside, "Here you go.\n\n" + inside + "\nDone."):
        files, err = extract_files(reply, [target])
        assert err is None, (task, reply[:60])
        assert files[target].strip() == code.strip()
