"""graders/hidden_seeds.py
Base seed definitions for Tier 3 evaluation.
See docs/07_GRADER_SPEC.md section 3.
"""
BASE_SEEDS: dict[str, int] = {
    "f1_fee_a": 1000,
    "f1_fee_b": 2000,
    "f2_replace_a": 3000,
    "f2_replace_b": 4000,
    "f3_fix_a": 5000,
    "f3_fix_b": 6000,
    "f4_waterfall_b": 7000,
    "f5_basket_b": 8000,
}


def get_task_seeds(task_id: str, count: int = 20) -> list[int]:
    """Return the list of hidden seeds for a task (Rule docs/07 section 3.2)."""
    base = BASE_SEEDS.get(task_id, 9000)
    return [base + i for i in range(count)]
