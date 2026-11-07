"""Grade model replies that were produced outside the API harness.

Used for the labelled, non-reproducible Claude Sonnet reference run: a reply text file is
extracted and graded with the same extractor and grader as `harness/run_eval.py`, and the
result is stored under results/claude/ (never mixed into results/main/).

    python tools/ingest_reply.py --label claude_sonnet --task f5_basket_b --trial 0 reply.txt
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from graders.dst_grader import grade_task  # noqa: E402
from harness.extract import extract_files  # noqa: E402
from harness.prompt import build_prompt_for_task  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("reply", type=Path)
    ap.add_argument("--label", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--trial", type=int, required=True)
    ap.add_argument("--out", type=Path, default=REPO / "results" / "claude")
    a = ap.parse_args()

    meta = tomllib.loads((REPO / "tasks" / a.task / "task.toml").read_text(encoding="utf-8"))
    bp = build_prompt_for_task(a.task)
    text = a.reply.read_text(encoding="utf-8")
    files, err = extract_files(text, meta.get("target_files", []))
    d = a.out / "raw" / a.label / a.task / str(a.trial)
    d.mkdir(parents=True, exist_ok=True)
    (d / "prompt.txt").write_text(bp.user_prompt, encoding="utf-8")
    (d / "reply.txt").write_text(text, encoding="utf-8")
    for rel, content in files.items():
        p = d / "files" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    if err:
        rec = {"t1": 0.0, "t2": 0.0, "t3": 0.0, "score": 0.0, "passed": False, "error": err,
               "first_failure": None, "seed_failures": []}
    else:
        s = grade_task(a.task, files, is_candidate=True)
        rec = {"t1": s.t1, "t2": s.t2, "t3": s.t3, "score": s.score, "passed": s.passed,
               "error": s.error, "first_failure": s.first_failure,
               "seed_failures": s.seed_failures}
    rec.update({
        "model": a.label, "task_id": a.task, "trial": a.trial, "mode": "single_turn",
        "prompt_sha256": bp.prompt_sha256,
        "note": "interactive run, not through the API harness; not reproducible",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out / "trials.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"{a.task} trial {a.trial}: score {rec['score']:.3f} "
          f"{'PASS' if rec['passed'] else 'FAIL'} t1={rec['t1']:.2f} t2={rec['t2']:.2f} "
          f"t3={rec['t3']:.2f} error={rec['error']}")


if __name__ == "__main__":
    main()
