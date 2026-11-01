"""harness/prompt.py
Prompt builder for OrderBook-DST evaluation harness.
See docs/08_HARNESS_AND_STATS.md sections 2 and 3.
"""
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent

SYSTEM_MESSAGE = """You are a senior software engineer. You write Python code.
Follow the rules in the task exactly. Use integer arithmetic only.
Answer with the complete content of each target file.
Use this format for each file:

### FILE: <path>
```python
<complete file content>
```

Write no other text outside these blocks."""

READONLY_CONTEXT_FILES = [
    "exchange_core/types.py",
    "exchange_core/state.py",
    "exchange_core/intmath.py",
    "exchange_core/config.py",
    "exchange_core/book.py",
    "exchange_core/ledger.py",
]


@dataclass(frozen=True)
class BuiltPrompt:
    system: str
    user_prompt: str
    prompt_sha256: str


def build_prompt_for_task(task_id: str) -> BuiltPrompt:
    """Build the prompt for a task according to docs/08 section 2."""
    task_dir = REPO_ROOT / "tasks" / task_id
    task_toml = task_dir / "task.toml"
    if not task_toml.exists():
        raise FileNotFoundError(f"task.toml not found for task {task_id}")

    meta: dict[str, Any] = tomli.loads(task_toml.read_text(encoding="utf-8"))
    instruction_file = task_dir / "instruction.md"
    instruction_text = (
        instruction_file.read_text(encoding="utf-8") if instruction_file.exists() else ""
    )

    parts: list[str] = []
    # 1. Instruction
    parts.append(instruction_text.strip())

    # 2. Target file stubs
    parts.append("\n## Target Files to Implement\n")
    target_files = meta.get("target_files", [])
    for rel_path in target_files:
        stub_file = task_dir / "workspace" / rel_path
        if stub_file.exists():
            content = stub_file.read_text(encoding="utf-8")
        else:
            ref_file = REPO_ROOT / "reference" / task_id / Path(rel_path).name
            content = ref_file.read_text(encoding="utf-8") if ref_file.exists() else ""

        parts.append(f"### Stub: {rel_path}\n```python\n{content.strip()}\n```")

    # 3. Read-only context files
    parts.append("\n## Reference Context (Read-Only)\n")
    for rel_path in READONLY_CONTEXT_FILES:
        ctx_file = REPO_ROOT / rel_path
        if ctx_file.exists():
            content = ctx_file.read_text(encoding="utf-8")
            parts.append(f"### Context: {rel_path}\n```python\n{content.strip()}\n```")

    user_prompt = "\n\n".join(parts)
    full_text = f"{SYSTEM_MESSAGE}\n\n{user_prompt}"
    sha256 = hashlib.sha256(full_text.encode("utf-8")).hexdigest()

    return BuiltPrompt(
        system=SYSTEM_MESSAGE,
        user_prompt=user_prompt,
        prompt_sha256=sha256,
    )
