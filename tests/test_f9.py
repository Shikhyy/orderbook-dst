"""tests/test_f9.py
The F9 "diagnose and fix" tasks: a buggy handler plus a symptom, graded by the grader of the
task named in `grades_as`.

What must hold:
- the prompts of the 11 existing tasks are byte-identical to what they were before F9;
- the committed F9 files are exactly what tools/make_f9.py generates (so the symptom
  reproduces from the stored seed, and nothing was edited by hand);
- each task's reference, clean-room alternative and minimal hand-written fix score 1.0 and
  the buggy file scores below 1.0 exactly like the mutant it was made from;
- the prompt names neither the mutant nor the fix.
"""
import ast
import json
from pathlib import Path
from typing import Any

import pytest

try:
    import tomllib as tomli
except ImportError:  # pragma: no cover
    import tomli  # type: ignore

from graders.dst_grader import grade_task
from graders.hidden_seeds import BASE_SEEDS, get_task_seeds
from harness.prompt import build_prompt_for_task
from tools import make_f9 as m

REPO = Path(__file__).resolve().parent.parent
IDS = [inst["id"] for inst in m.INSTANCES]
BY_ID = {inst["id"]: inst for inst in m.INSTANCES}


def _meta(task_id: str) -> dict[str, Any]:
    return tomli.loads((REPO / "tasks" / task_id / "task.toml").read_text(encoding="utf-8"))


def test_there_are_six_instances_over_six_handlers() -> None:
    assert IDS == [f"f9_dbg_{i}" for i in range(1, 7)]
    targets = {tuple(_meta(i)["target_files"]) for i in IDS}
    assert len(targets) == 6


def test_existing_prompts_are_unchanged() -> None:
    baseline = json.loads(
        (REPO / "tests" / "f9_baseline_prompt_hashes.json").read_text(encoding="utf-8")
    )
    for task_id, expected in baseline.items():
        if (REPO / "tasks" / task_id / "workspace").exists():
            # A git-ignored local stub directory (make_workspace.py) legitimately changes
            # the prompt of that task; the fresh checkout has none.
            continue
        assert build_prompt_for_task(task_id).prompt_sha256 == expected, task_id


def test_generated_files_are_current() -> None:
    for rel, content in m.all_outputs().items():
        path = REPO / rel
        assert path.exists(), f"{rel} missing: run python tools/make_f9.py --write"
        assert path.read_text(encoding="utf-8") == content, (
            f"{rel} is stale: run python tools/make_f9.py --write"
        )


def test_visible_seeds_are_disjoint_from_every_hidden_range() -> None:
    hidden = {s for tid in BASE_SEEDS for s in get_task_seeds(tid, 20)}
    for inst in m.INSTANCES:
        if isinstance(inst["trace"], int):
            assert inst["trace"] not in hidden
            assert inst["trace"] >= m.VISIBLE_SEED_BASE


def test_symptom_kinds_are_varied() -> None:
    kinds = {
        json.loads((REPO / "tasks" / i / "symptom_meta.json").read_text())["kind"] for i in IDS
    }
    assert len(kinds) >= 3, kinds


@pytest.mark.parametrize("task_id", IDS)
def test_task_metadata(task_id: str) -> None:
    meta = _meta(task_id)
    inst = BY_ID[task_id]
    assert meta["family"] == "F9" and meta["mode"] == "debug"
    assert meta["grades_as"] == inst["base"]
    base = _meta(inst["base"])
    assert meta["target_files"] == base["target_files"]
    assert isinstance(meta["author_signoff"], bool)
    assert (REPO / "tasks" / task_id / "buggy" / meta["target_files"][0]).exists()


@pytest.mark.parametrize("task_id", IDS)
def test_prompt_shows_bug_report_and_buggy_file_not_a_stub(task_id: str) -> None:
    prompt = build_prompt_for_task(task_id)
    text = prompt.user_prompt
    assert "## Bug Report" in text
    assert "## Buggy Target Files (return the corrected file)" in text
    assert "## Target Files to Implement" not in text
    assert "NotImplementedError" not in text.split("## Buggy Target Files", 1)[1].split(
        "## Reference Context", 1
    )[0]
    assert "## Public Tests (Visible)" in text
    assert prompt.prompt_sha256 and len(prompt.prompt_sha256) == 64


@pytest.mark.parametrize("task_id", IDS)
def test_prompt_does_not_name_the_mutant_or_show_the_fix(task_id: str) -> None:
    inst = BY_ID[task_id]
    meta = _meta(task_id)
    prompt = build_prompt_for_task(task_id)
    full = f"{prompt.system}\n\n{prompt.user_prompt}"
    low = full.lower()
    assert "mutant" not in low
    assert inst["mutant"] not in full
    assert meta["source_mutant"] not in full
    assert meta["difficulty_reason"] not in full
    desc = REPO / "mutants" / inst["base"] / inst["mutant"] / "DESCRIPTION.txt"
    if desc.exists():
        assert desc.read_text(encoding="utf-8").strip() not in full
    # No visible hidden seed.
    for s in get_task_seeds(inst["base"], 20):
        assert f"seed={s}" not in full and f"seed {s}" not in full
    # No checkpoint content from the targeted trace.
    assert "expected_reports" not in full and "tier2_trace" not in full

    # The fix itself: every executable reference line that the buggy file lacks must be
    # absent from the whole prompt (the spec may describe behaviour, but not paste the code).
    buggy_lines = {
        ln.strip()
        for src in m.buggy_sources(inst).values()
        for ln in src.splitlines()
    }
    for src in m.reference_files(inst["base"]).values():
        tree = ast.parse(src)
        lines = src.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.If, ast.For, ast.Return)):
                line = lines[node.lineno - 1].strip()
                if len(line) > 20 and line not in buggy_lines:
                    assert line not in full, f"prompt leaks fix line: {line}"


@pytest.mark.parametrize("task_id", IDS)
def test_buggy_file_has_no_comment_or_docstring_naming_the_bug(task_id: str) -> None:
    for src in m.buggy_sources(BY_ID[task_id]).values():
        low = src.lower()
        assert "mutant" not in low and "bug" not in low


@pytest.mark.parametrize("task_id", IDS)
def test_symptom_reproduces_from_the_stored_trace(task_id: str) -> None:
    inst = BY_ID[task_id]
    sym, text, events = m.symptom_for(inst)
    stored = (REPO / "tasks" / task_id / "symptom.md").read_text(encoding="utf-8")
    assert stored == text
    meta = json.loads((REPO / "tasks" / task_id / "symptom_meta.json").read_text())
    assert meta["kind"] == sym["kind"] and meta["index"] == sym["index"]
    # The trace shown stops at the failing event and every event is listed.
    assert f"{sym['index']}. " in stored
    assert f"{sym['index'] + 1}. " not in stored


@pytest.mark.parametrize("task_id", IDS)
def test_buggy_scores_below_one_like_its_mutant_and_every_fix_scores_one(task_id: str) -> None:
    inst = BY_ID[task_id]
    base = inst["base"]
    meta = _meta(base)
    buggy = grade_task(task_id, m.buggy_sources(inst), is_candidate=True)
    mutant = grade_task(base, m.mutant_files(base, inst["mutant"]), is_candidate=True)
    assert buggy.error is None
    assert buggy.score < 1.0 and not buggy.passed
    assert (buggy.t1, buggy.t2, buggy.t3) == (mutant.t1, mutant.t2, mutant.t3)

    fixed = grade_task(task_id, m.fixed_sources(inst), is_candidate=True)
    assert fixed.score == 1.0 and fixed.passed
    reference = grade_task(task_id, m.reference_files(base), is_candidate=True)
    assert reference.score == 1.0
    alt = {
        rel: (REPO / "reference_alt_v2" / base / Path(rel).name).read_text(encoding="utf-8")
        for rel in meta["target_files"]
    }
    assert grade_task(task_id, alt, is_candidate=True).score == 1.0


@pytest.mark.parametrize("task_id", IDS)
def test_f9_task_is_graded_with_the_hidden_seeds_of_its_base_task(task_id: str) -> None:
    # grades_as must reach the base task's hidden seeds and profile: a candidate that is
    # wrong only under a hidden seed of the base task must be caught.
    inst = BY_ID[task_id]
    buggy = grade_task(task_id, m.buggy_sources(inst), is_candidate=True)
    base_rec = grade_task(
        inst["base"], m.mutant_files(inst["base"], inst["mutant"]), is_candidate=True
    )
    assert buggy.first_failure == base_rec.first_failure


def _reply(rel_path_to_src: dict[str, str]) -> str:
    return "".join(
        f"### FILE: {rel}\n```python\n{src}\n```\n" for rel, src in rel_path_to_src.items()
    )


def test_harness_runs_f9_tasks_end_to_end_with_a_mock_model(tmp_path: Path) -> None:
    """Prompt, reply extraction, grading and the trial record all work for debug tasks."""
    import harness.run_eval as re_mod
    from harness.adapters.mock import MockAdapter

    fixed = [_reply(m.fixed_sources(BY_ID[i])) for i in IDS]
    buggy_first = [_reply(m.buggy_sources(BY_ID[IDS[0]]))] + fixed[1:]
    adapter = MockAdapter(responses=buggy_first)
    orig = re_mod.get_adapter
    re_mod.get_adapter = lambda _: adapter
    try:
        re_mod.run_single_turn_eval(
            [{"label": "mock_m", "adapter": "mock", "model_id": "mock-v1", "trials": 1}],
            IDS, tmp_path, 1,
        )
    finally:
        re_mod.get_adapter = orig
    rows = [
        json.loads(ln) for ln in (tmp_path / "trials.jsonl").read_text().splitlines() if ln
    ]
    by_task = {r["task_id"]: r for r in rows}
    assert set(by_task) == set(IDS)
    assert by_task[IDS[0]]["passed"] is False and by_task[IDS[0]]["score"] < 1.0
    assert all(by_task[i]["passed"] and by_task[i]["score"] == 1.0 for i in IDS[1:])
    prompt = (tmp_path / "raw" / "mock_m" / IDS[0] / "0" / "prompt.txt").read_text()
    assert "## Bug Report" in prompt


def test_feedback_loop_works_for_an_f9_task(tmp_path: Path) -> None:
    import harness.run_eval as re_mod
    from harness.adapters.mock import MockAdapter

    task_id = "f9_dbg_4"
    inst = BY_ID[task_id]
    adapter = MockAdapter(
        responses=[_reply(m.buggy_sources(inst)), _reply(m.fixed_sources(inst))]
    )
    orig = re_mod.get_adapter
    re_mod.get_adapter = lambda _: adapter
    try:
        re_mod.run_feedback_loop_eval(
            models_cfg=[{"label": "mock_m", "adapter": "mock", "model_id": "mock-v1", "trials": 1}],
            task_ids=[task_id], out_dir=tmp_path, trials_override=1, max_revisions=2,
        )
    finally:
        re_mod.get_adapter = orig
    trial_dir = tmp_path / "raw" / "mock_m" / task_id / "0"
    assert (trial_dir / "feedback_revision_1.txt").exists()
    score = json.loads((trial_dir / "score.json").read_text())
    assert score["passed"] is True


def test_report_keeps_f9_out_of_the_headline_and_adds_its_own_section(tmp_path: Path) -> None:
    from harness.report import generate_report

    def row(task: str, passed: bool, score: float) -> dict[str, Any]:
        return {
            "model": "m1", "model_id": "x", "tier": "mid", "task_id": task, "trial": 0,
            "mode": "single_turn", "passed": passed, "score": score, "t1": score, "t2": score,
            "t3": score, "error": None, "first_failure": None, "seed_failures": [],
            "settings": {}, "cost_usd_est": 0.0, "latency_s": 1.0,
        }

    rows = [row("f4_waterfall_b", True, 1.0), row("f9_dbg_2", False, 0.5278)]
    (tmp_path / "trials.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    data = generate_report(tmp_path, tmp_path / "out")
    assert data["models"][0]["trials_count"] == 1
    assert [p["task_id"] for p in data["models"][0]["per_task"]] == ["f4_waterfall_b"]
    assert data["total_trials"] == 2
    task = data["debug"][0]["tasks"][0]
    assert task["task_id"] == "f9_dbg_2" and task["graded_as"] == "f4_waterfall_b"
    assert task["passes"] == 0 and task["base_passes"] == 1 and task["base_trials"] == 1
    md = (tmp_path / "out" / "summary.md").read_text(encoding="utf-8")
    assert "F9: diagnose and fix" in md and "impl 1/1" in md
    headline = md.split("## F9: diagnose and fix", 1)[0]
    assert "f9_dbg_2" not in headline
