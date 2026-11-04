"""tools/make_demo.py
30-second demo of the grader, with no API keys.

Grades two versions of exchange_core/handlers/replace.py for task f2_replace_b:
  1. the reference solution, which passes every tier;
  2. mutant m_lock_uses_current_rate, a one-line realistic bug (re-locking margin
     at the engine's current rate instead of the order's original rate). It
     passes every visible test and every checkpoint; only the hidden
     deterministic simulation traces catch it, through invariant I2.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from graders.dst_grader import grade_task  # noqa: E402

TASK = "f2_replace_b"
TARGET = "exchange_core/handlers/replace.py"
VERSIONS = [
    ("reference solution", REPO_ROOT / "reference" / TASK / "replace.py"),
    ("bug: m_lock_uses_current_rate",
     REPO_ROOT / "mutants" / TASK / "m_lock_uses_current_rate" / "replace.py"),
]


def main() -> None:
    print(f"Task {TASK}: {TARGET}\n")
    for name, path in VERSIONS:
        rec = grade_task(TASK, {TARGET: path.read_text(encoding="utf-8")}, is_candidate=True)
        verdict = "PASS" if rec.passed else "FAIL"
        print(f"{name}")
        print(f"  T1 visible tests : {rec.t1:.2f}")
        print(f"  T2 checkpoints   : {rec.t2:.2f}")
        print(f"  T3 hidden traces : {rec.t3:.2f}  ({round(rec.t3 * 20)} / 20 seeds)")
        print(f"  score {rec.score:.2f} -> {verdict}")
        ff = rec.first_failure
        if ff:
            print(f"  first failure: seed {ff['seed']}, event {ff['event_index']}, "
                  f"{ff['invariant']} ({ff['plain_name']}): {ff['message']}")
        print()


if __name__ == "__main__":
    main()
