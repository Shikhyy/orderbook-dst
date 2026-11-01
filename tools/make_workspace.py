"""tools/make_workspace.py
Workspace generator for OrderBook-DST benchmark tasks.
See docs/06_TASK_SPECS.md section 2 and docs/07_GRADER_SPEC.md section 6.
"""
import argparse
import shutil
from pathlib import Path
from typing import Any

try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent

STUB_TEMPLATES: dict[str, str] = {
    "exchange_core/rules/replace_rule.py": '''"""exchange_core/rules/replace_rule.py
Pure function for replace decisions.
Rules R-P1, R-P2 (steps 2, 3), and R-P3. Target for task f2_replace_a.
"""
from exchange_core.config import EngineConfig
from exchange_core.types import Order, ReplaceDecision


def decide_replace(
    order: Order,
    new_price: int,
    new_qty: int,
    cfg: EngineConfig,
) -> ReplaceDecision:
    """Decide whether a replace request is valid and whether it keeps priority.

    Rules R-P1, R-P2 (steps 2 and 3), R-P3.
    """
    raise NotImplementedError("Implement decide_replace")
''',
    "exchange_core/handlers/replace.py": '''"""exchange_core/handlers/replace.py
Handle REPLACE event.
Rules R-P1 to R-P4. Target for task f2_replace_b.
"""
from exchange_core.types import Event, Report


def handle_replace(engine: "Engine", event: Event) -> list[Report]:  # type: ignore # noqa: F821
    """Process a REPLACE event according to rules R-P1 to R-P4."""
    raise NotImplementedError("Implement handle_replace")
''',
}


def build_workspace_for_task(task_id: str) -> None:
    task_dir = REPO_ROOT / "tasks" / task_id
    task_toml = task_dir / "task.toml"
    if not task_toml.exists():
        print(f"Skipping {task_id}: task.toml not found")
        return

    meta: dict[str, Any] = tomli.loads(task_toml.read_text(encoding="utf-8"))
    workspace_dir = task_dir / "workspace"
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy exchange_core
    core_src = REPO_ROOT / "exchange_core"
    core_dst = workspace_dir / "exchange_core"
    shutil.copytree(core_src, core_dst)

    # 2. Stub target files
    target_files = meta.get("target_files", [])
    for rel_path in target_files:
        dst_target = workspace_dir / rel_path
        dst_target.parent.mkdir(parents=True, exist_ok=True)
        if rel_path in STUB_TEMPLATES:
            dst_target.write_text(STUB_TEMPLATES[rel_path], encoding="utf-8")
        else:
            dst_target.write_text(
                'raise NotImplementedError("Implement candidate function")\n',
                encoding="utf-8",
            )

    # 3. Copy public tests into workspace/tests
    pub_tests = task_dir / "public_tests"
    tests_dst = workspace_dir / "tests"
    if pub_tests.exists():
        shutil.copytree(pub_tests, tests_dst)

    # 4. Copy conftest.py if present
    conftest = REPO_ROOT / "conftest.py"
    if conftest.exists():
        shutil.copy2(conftest, workspace_dir / "conftest.py")

    # 5. Create workspace README.md in ASD-STE100
    readme_text = f"""# Workspace for Task: {task_id}

## Instructions

1. Read `../instruction.md` for task requirements and rules.
2. Edit only the target file:
{chr(10).join(f"   - `{f}`" for f in target_files)}
3. Run tests with:
   ```bash
   pytest tests/
   ```
4. Do not modify other files in `exchange_core/`.
5. Use integer arithmetic only.
"""
    (workspace_dir / "README.md").write_text(readme_text, encoding="utf-8")

    # 6. Create .gitignore
    (workspace_dir / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.pytest_cache/\n", encoding="utf-8"
    )
    print(f"Built workspace for {task_id} at {workspace_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build task workspaces")
    parser.add_argument("--task", type=str, help="Specific task ID to build")
    args = parser.parse_args()

    tasks_dir = REPO_ROOT / "tasks"
    if args.task:
        build_workspace_for_task(args.task)
    else:
        for t in sorted(tasks_dir.iterdir()):
            if t.is_dir() and (t / "task.toml").exists():
                build_workspace_for_task(t.name)


if __name__ == "__main__":
    main()
