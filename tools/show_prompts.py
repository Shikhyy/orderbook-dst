"""tools/show_prompts.py
Generate and print prompt text and byte sizes for all 8 tasks into scratch/prompts/<task>.txt.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness.prompt import build_prompt_for_task  # noqa: E402

TASKS = [
    "f1_fee_a",
    "f1_fee_b",
    "f2_replace_a",
    "f2_replace_b",
    "f3_fix_a",
    "f3_fix_b",
    "f4_waterfall_b",
    "f5_basket_b",
]


def generate_all_prompts() -> dict[str, int]:
    out_dir = REPO_ROOT / "scratch" / "prompts"
    out_dir.mkdir(parents=True, exist_ok=True)

    sizes: dict[str, int] = {}
    for task_id in TASKS:
        prompt = build_prompt_for_task(task_id)
        content = (
            f"=== SYSTEM PROMPT ===\n{prompt.system}\n\n"
            f"=== USER PROMPT ===\n{prompt.user_prompt}\n"
        )
        dest = out_dir / f"{task_id}.txt"
        dest.write_text(content, encoding="utf-8")
        byte_size = dest.stat().st_size
        sizes[task_id] = byte_size
        print(f"Task: {task_id:<16} Path: {dest.relative_to(REPO_ROOT)} ({byte_size:,} bytes)")
    return sizes


if __name__ == "__main__":
    generate_all_prompts()
