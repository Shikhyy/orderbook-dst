"""Rate limiting for free API tiers: retries, daily caps, and clean resume."""
import json
from pathlib import Path
from typing import Any

import pytest

from harness.adapters.base import ModelReply
from harness.ratelimit import ModelUnavailable, RateLimitedAdapter


class ApiError(Exception):
    def __init__(self, status: int, msg: str = "", retry_after: str | None = None):
        super().__init__(msg)
        self.status_code = status
        headers = {"retry-after": retry_after} if retry_after else {}
        self.response = type("R", (), {"headers": headers, "status_code": status})()


class Scripted:
    name = "scripted"

    def __init__(self, outcomes: list[Any]):
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate(self, system: str, prompt: str, settings: dict) -> ModelReply:
        self.calls += 1
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return ModelReply(text=o, input_tokens=1, output_tokens=1, latency_s=0.0, raw_meta={})


def _wrap(inner, **kw):
    sleeps: list[float] = []
    w = RateLimitedAdapter(inner, "m", sleep=sleeps.append, clock=lambda: 0.0, **kw)
    return w, sleeps


def test_retries_rate_limit_then_succeeds_with_backoff_and_retry_after():
    inner = Scripted(
        [ApiError(429, "slow down"), ApiError(503), ApiError(429, retry_after="7"), "ok"]
    )
    w, sleeps = _wrap(inner, base_delay_s=2.0)
    assert w.generate("s", "p", {}).text == "ok"
    assert sleeps == [2.0, 4.0, 7.0]
    assert w.retries == 3


def test_daily_quota_stops_model_without_retrying():
    inner = Scripted([ApiError(429, "Quota exceeded for requests per day")])
    w, sleeps = _wrap(inner)
    with pytest.raises(ModelUnavailable, match="daily quota"):
        w.generate("s", "p", {})
    assert inner.calls == 1 and sleeps == []


def test_auth_error_is_not_retried():
    inner = Scripted([ApiError(401, "invalid key")])
    w, _ = _wrap(inner)
    with pytest.raises(ModelUnavailable, match="giving up after 0 retries"):
        w.generate("s", "p", {})


def test_retries_are_bounded():
    inner = Scripted([ApiError(500)] * 3)
    w, _ = _wrap(inner, max_retries=2)
    with pytest.raises(ModelUnavailable):
        w.generate("s", "p", {})
    assert inner.calls == 3


def test_rpd_cap_and_rpm_spacing():
    t = [0.0]
    sleeps: list[float] = []
    inner = Scripted(["a", "b", "c"])
    w = RateLimitedAdapter(inner, "m", rpm=30, rpd=2,
                           sleep=lambda d: (sleeps.append(d), t.__setitem__(0, t[0] + d)),
                           clock=lambda: t[0])
    w.generate("s", "p", {})
    w.generate("s", "p", {})
    assert sleeps == [2.0]  # 30 rpm -> 2 s between calls
    with pytest.raises(ModelUnavailable, match="rpd=2"):
        w.generate("s", "p", {})


def test_run_skips_exhausted_model_and_resumes(tmp_path: Path, monkeypatch):
    """A quota stop records nothing for unfinished trials; the next run fills them in."""
    import harness.run_eval as re

    ref = Path("reference/f1_fee_a/fee_rule.py").read_text()
    reply = f"### FILE: exchange_core/rules/fee_rule.py\n```python\n{ref}\n```\n"
    plan = {"a": Scripted([reply, ApiError(429, "daily quota exhausted")]),
            "b": Scripted([reply, reply])}
    monkeypatch.setattr(re, "get_adapter", lambda name: plan.pop(next(iter(plan))))
    cfg = [{"label": "a", "adapter": "mock", "model_id": "x", "trials": 2},
           {"label": "b", "adapter": "mock", "model_id": "y", "trials": 2}]
    re.run_single_turn_eval(cfg, ["f1_fee_a"], tmp_path, None)
    recs = [json.loads(x) for x in (tmp_path / "trials.jsonl").read_text().splitlines()]
    assert sorted((r["model"], r["trial"]) for r in recs) == [("a", 0), ("b", 0), ("b", 1)]
    assert all(r["passed"] for r in recs)

    plan = {"a": Scripted([reply])}
    monkeypatch.setattr(re, "get_adapter", lambda name: plan.pop("a"))
    re.run_single_turn_eval(cfg[:1], ["f1_fee_a"], tmp_path, None)
    recs = [json.loads(x) for x in (tmp_path / "trials.jsonl").read_text().splitlines()]
    assert sorted((r["model"], r["trial"]) for r in recs) == [
        ("a", 0), ("a", 1), ("b", 0), ("b", 1)
    ]


def _timed(latency: float):
    class T:
        name = "t"

        def generate(self, system, prompt, settings):
            return ModelReply(text="x", latency_s=latency)

    return T()


def test_budget_stops_before_a_call_that_could_exceed_it():
    from harness.ratelimit import wrap_for_model

    m = {"label": "modal", "budget_usd": 0.10, "usd_per_second": 0.01}
    w = wrap_for_model(_timed(4.0), m)  # each call is estimated at $0.04
    w.generate("s", "p", {})  # spent 0.04
    w.generate("s", "p", {})  # spent 0.08; next call would reach 0.12 > 0.10
    assert abs(w.spent_usd - 0.08) < 1e-9
    with pytest.raises(ModelUnavailable, match="budget"):
        w.generate("s", "p", {})


def test_budget_holds_across_resumes_and_needs_a_rate():
    from harness.ratelimit import wrap_for_model

    m = {"label": "modal", "budget_usd": 0.10, "usd_per_second": 0.01}
    w = wrap_for_model(_timed(4.0), m, spent_usd=0.09)  # earlier runs spent $0.09
    w.generate("s", "p", {})  # no last-call estimate yet, so the first call is allowed
    with pytest.raises(ModelUnavailable, match="budget"):
        w.generate("s", "p", {})
    with pytest.raises(ValueError, match="usd_per_second"):
        wrap_for_model(_timed(1.0), {"label": "x", "budget_usd": 1.0})


def test_prior_spend_and_task_subset_and_only_flag(tmp_path):
    import json

    from harness.run_eval import prior_spend_usd, tasks_for_model

    f = tmp_path / "trials.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in [
        {"model": "modal", "latency_s": 10}, {"model": "modal", "latency_s": 5},
        {"model": "other", "latency_s": 99},
    ]) + "\n")
    assert prior_spend_usd(f, {"label": "modal", "usd_per_second": 0.01}) == pytest.approx(0.15)
    assert prior_spend_usd(f, {"label": "modal"}) == 0.0
    assert tasks_for_model({"tasks": ["b"]}, ["a", "b", "c"]) == ["b"]
    assert tasks_for_model({}, ["a", "b"]) == ["a", "b"]


def test_empty_reply_is_retried_a_bounded_number_of_times_and_recorded():
    empty = ModelReply(text="", raw_meta={"finish_reason": "tool_calls"})

    class Seq:
        name = "s"

        def __init__(self, replies):
            self.replies = list(replies)
            self.calls = 0

        def generate(self, system, prompt, settings):
            self.calls += 1
            return self.replies.pop(0)

    inner = Seq([empty, ModelReply(text="answer")])
    w, _ = _wrap(inner)
    out = w.generate("s", "p", {})
    assert out.text == "answer" and out.raw_meta["empty_retries"] == 1 and inner.calls == 2

    inner = Seq([ModelReply(text=""), ModelReply(text=""), ModelReply(text="  ")])
    w, _ = _wrap(inner)
    out = w.generate("s", "p", {})  # gives up after 2 retries and returns the empty reply
    assert out.text.strip() == "" and out.raw_meta["empty_retries"] == 2 and inner.calls == 3


GROQ_TPM_429 = (
    "Error code: 429 - Rate limit reached for model `openai/gpt-oss-20b` ... on tokens per "
    "minute (TPM): Limit 8000, Used 5341, Requested 7938. Please try again in 39.5925s. "
    "Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing"
)
GROQ_413 = (
    "Error code: 413 - Request too large for model `openai/gpt-oss-120b` ... on tokens per "
    "minute (TPM): Limit 8000, Requested 8218, please reduce your message size and try again."
)


def test_groq_per_minute_429_is_waited_out_not_called_a_daily_quota():
    from harness.ratelimit import is_daily_quota, retry_in_message

    err = ApiError(429, GROQ_TPM_429)
    assert not is_daily_quota(err)  # the "billing" link in the text used to trip this
    assert retry_in_message(err) == pytest.approx(39.5925)
    inner = Scripted([err, "ok"])
    w, sleeps = _wrap(inner)
    assert w.generate("s", "p", {}).text == "ok"
    assert sleeps == [pytest.approx(40.5925)]


def test_real_daily_cap_and_gemini_per_minute_messages():
    from harness.ratelimit import is_daily_quota

    assert is_daily_quota(ApiError(429, "Rate limit ... requests per day (RPD): Limit 1000"))
    assert is_daily_quota(ApiError(429, "Free usage limit reached for today, daily quota"))
    assert not is_daily_quota(ApiError(429, "Quota exceeded for metric ... PerMinute"))
    assert not is_daily_quota(ApiError(429, "Rate limit exceeded"))


def test_request_too_large_skips_the_task_not_the_model():
    from harness.ratelimit import RequestTooLarge

    w, sleeps = _wrap(Scripted([ApiError(413, GROQ_413)]))
    with pytest.raises(RequestTooLarge):
        w.generate("s", "p", {})
    assert sleeps == []  # not retried
    assert issubclass(RequestTooLarge, ModelUnavailable)


def test_run_skips_an_oversized_task_and_continues_with_the_next(tmp_path, monkeypatch):
    import harness.run_eval as re

    ref = Path("reference/f2_replace_a/replace_rule.py").read_text()
    reply = f"### FILE: exchange_core/rules/replace_rule.py\n```python\n{ref}\n```\n"

    class Picky:
        name = "picky"

        def generate(self, system, prompt, settings):
            if "Task f1_fee_a" in prompt:
                raise ApiError(413, GROQ_413)
            return ModelReply(text=reply, input_tokens=9999, latency_s=0.0)

    monkeypatch.setattr(re, "get_adapter", lambda name: Picky())
    cfg = [{"label": "p", "adapter": "mock", "model_id": "x", "trials": 2}]
    re.run_single_turn_eval(cfg, ["f1_fee_a", "f2_replace_a"], tmp_path, None)
    recs = [json.loads(x) for x in (tmp_path / "trials.jsonl").read_text().splitlines()]
    assert [(r["task_id"], r["trial"]) for r in recs] == [("f2_replace_a", 0), ("f2_replace_a", 1)]
    prog = json.loads((tmp_path / "progress.json").read_text())
    assert prog["done"] == prog["total"] == 4 and len(prog["skipped"]) == 1
    assert prog["stopped"] == []


def test_out_of_tokens_empty_reply_is_not_retried_and_is_classified():
    from harness.extract import classify_extract_error

    class Seq:
        name = "s"
        calls = 0

        def generate(self, system, prompt, settings):
            self.calls += 1
            return ModelReply(text="", raw_meta={"finish_reason": "length"})

    inner = Seq()
    w, _ = _wrap(inner)
    out = w.generate("s", "p", {})
    assert inner.calls == 1 and out.raw_meta["empty_retries"] == 0
    assert classify_extract_error("FORMAT_ERROR", "length") == "OUTPUT_TRUNCATED"
    assert classify_extract_error("FORMAT_ERROR", "stop") == "FORMAT_ERROR"
    assert classify_extract_error(None, "length") is None
