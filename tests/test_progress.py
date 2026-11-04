"""Progress reporting: counters, announced waits, heartbeat file, status snapshot."""
import json
from pathlib import Path

import harness.run_eval as re
from harness.adapters.base import ModelReply
from tools.status import snapshot

REF = Path("reference/f1_fee_a/fee_rule.py").read_text()
REPLY = f"### FILE: exchange_core/rules/fee_rule.py\n```python\n{REF}\n```\n"


class Stub:
    name = "stub"

    def generate(self, system, prompt, settings):
        return ModelReply(text=REPLY, input_tokens=9999, output_tokens=5, latency_s=1.0)


def test_run_prints_counters_writes_heartbeat_and_status_reads_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(re, "get_adapter", lambda name: Stub())
    cfg = [{"label": "stub", "adapter": "mock", "model_id": "x", "trials": 2}]
    re.run_single_turn_eval(cfg, ["f1_fee_a"], tmp_path, None)

    out = capsys.readouterr().out
    assert "[0/2]" in out and "[1/2]" in out and "[2/2]" in out
    assert "stub | f1_fee_a | trial 1/2: calling model" in out
    assert "score 1.00 PASS" in out and "run finished" in out

    prog = json.loads((tmp_path / "progress.json").read_text())
    assert prog["state"] == "finished" and prog["done"] == 2 and prog["total"] == 2
    assert prog["expected"] == {"stub": 2}

    text = snapshot(tmp_path, {})
    assert "State: finished" in text and "2/2 (100%)" in text and "stub" in text


def test_rate_limit_wait_is_announced_in_the_log(tmp_path, monkeypatch, capsys):
    import harness.ratelimit as rl

    slept: list[float] = []
    monkeypatch.setattr(rl.time, "sleep", slept.append)
    t = iter(range(0, 10_000, 1))
    monkeypatch.setattr(rl.time, "monotonic", lambda: float(next(t)))
    monkeypatch.setattr(re, "get_adapter", lambda name: Stub())
    cfg = [{"label": "slow", "adapter": "mock", "model_id": "x", "trials": 2, "rpm": 1}]
    re.run_single_turn_eval(cfg, ["f1_fee_a"], tmp_path, None)
    out = capsys.readouterr().out
    assert "waiting" in out and "rate limit (1 requests/min)" in out
    assert slept and max(slept) > 3


def test_status_reports_a_dead_run(tmp_path):
    (tmp_path / "progress.json").write_text(json.dumps(
        {"pid": 99999999, "state": "running", "done": 3, "total": 10, "updated": 0, "current": {}}
    ))
    text = snapshot(tmp_path, {})
    assert "NOT RUNNING" in text and "resume" in text
