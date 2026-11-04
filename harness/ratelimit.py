"""harness/ratelimit.py
Rate limiting and retries for model calls, so runs on free API tiers finish.

Free tiers return HTTP 429 when a per-minute or per-day cap is hit, and
sometimes 5xx or timeouts. The wrapper:
  - spaces calls to stay under `rpm` (requests per minute) for that model,
  - stops after `rpd` calls in this run (requests per day), so a daily cap is
    never hit mid-trial,
  - retries retryable errors with exponential backoff, honouring Retry-After,
  - raises ModelUnavailable when a model cannot be called any more. The run
    then skips that model without writing a record, so the unfinished trials
    are picked up by the next resume (the same command, run again later).

An API failure is never recorded as a model failure.
"""
import re
import time
from typing import Any, Callable, Optional

from harness.adapters.base import ModelReply

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}
RETRYABLE_NAMES = ("Timeout", "Connection", "RateLimit", "Overloaded", "InternalServer")
DAY_HINTS = ("per day", "perday", "requests per day", "daily", "rpd")
MINUTE_HINTS = ("per minute", "perminute", "tpm", "rpm", "try again in", "retry in")
TOKEN_LIMIT_REASONS = ("length", "max_tokens")
TOO_LARGE_HINTS = ("request too large", "reduce your message size", "context length",
                   "maximum context", "too many tokens")


class ModelUnavailable(Exception):
    """The model cannot be called again in this run (quota, auth, or retries used up)."""


class RequestTooLarge(ModelUnavailable):
    """This request exceeds the provider's per-request token limit for the model.

    Waiting does not help, but other (smaller) requests may still work, so the run
    skips this task instead of stopping the model.
    """


def _status(exc: BaseException) -> Optional[int]:
    for attr in ("status_code", "status", "code"):
        v = getattr(exc, attr, None)
        if isinstance(v, int):
            return v
    resp = getattr(exc, "response", None)
    v = getattr(resp, "status_code", None)
    return v if isinstance(v, int) else None


def _retry_after(exc: BaseException) -> Optional[float]:
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None)
    if not headers:
        return None
    try:
        raw = headers.get("retry-after") or headers.get("Retry-After")
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def is_retryable(exc: BaseException) -> bool:
    status = _status(exc)
    if status is not None:
        return status in RETRYABLE_STATUS
    return any(n in type(exc).__name__ for n in RETRYABLE_NAMES)


def is_daily_quota(exc: BaseException) -> bool:
    """A 429 about a per-day cap. A per-minute message wins, because it clears by waiting."""
    msg = str(exc).lower()
    return (
        _status(exc) == 429
        and any(h in msg for h in DAY_HINTS)
        and not any(h in msg for h in MINUTE_HINTS)
    )


def is_request_too_large(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return _status(exc) == 413 or (
        _status(exc) in (400, 422) and any(h in msg for h in TOO_LARGE_HINTS)
    )


def retry_in_message(exc: BaseException) -> Optional[float]:
    """Seconds from a "try again in 39.59s" / "in 250ms" / "in 2m" style message."""
    m = re.search(r"(?:try again|retry) in ([0-9.]+)\s*(ms|s|m)\b", str(exc).lower())
    if not m:
        return None
    value, unit = float(m.group(1)), m.group(2)
    return value / 1000 if unit == "ms" else value * 60 if unit == "m" else value


class RateLimitedAdapter:
    """Wraps any adapter with the same generate() signature."""

    def __init__(
        self,
        inner: Any,
        label: str,
        rpm: Optional[float] = None,
        rpd: Optional[int] = None,
        max_retries: int = 6,
        max_empty_retries: int = 2,
        budget_usd: Optional[float] = None,
        usd_per_second: float = 0.0,
        spent_usd: float = 0.0,
        base_delay_s: float = 5.0,
        max_delay_s: float = 120.0,
        sleep: Optional[Callable[[float], None]] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self.inner = inner
        self.name = getattr(inner, "name", "wrapped")
        self.label = label
        self.min_interval = 60.0 / rpm if rpm else 0.0
        self.rpd = rpd
        self.max_retries = max_retries
        self.max_empty_retries = max_empty_retries
        self.budget_usd = budget_usd
        self.usd_per_second = usd_per_second
        self.spent_usd = spent_usd
        self.last_call_usd = 0.0
        self.base_delay_s = base_delay_s
        self.max_delay_s = max_delay_s
        # Looked up at call time (not bound at import) so tests can patch time.
        self._sleep: Callable[[float], None] = sleep or (lambda d: time.sleep(d))
        self._clock: Callable[[], float] = clock or (lambda: time.monotonic())
        self._last_call: Optional[float] = None
        self.notify: Callable[[str], None] = print  # progress hook; replaced by the run loop
        self.calls = 0
        self.retries = 0

    def _space_out(self) -> None:
        if self.min_interval and self._last_call is not None:
            wait = self.min_interval - (self._clock() - self._last_call)
            if wait > 0:
                if wait >= 3:
                    self.notify(f"[{self.label}] waiting {wait:.0f}s to stay under the "
                                f"rate limit ({60.0 / self.min_interval:g} requests/min)")
                self._sleep(wait)
        self._last_call = self._clock()

    def generate(self, system: str, prompt: str, settings: dict[str, Any]) -> ModelReply:
        if self.rpd is not None and self.calls >= self.rpd:
            raise ModelUnavailable(
                f"{self.label}: reached rpd={self.rpd} calls in this run; "
                "run the same command again after the provider's daily reset to resume"
            )
        if self.budget_usd is not None and (
            self.spent_usd + self.last_call_usd > self.budget_usd
        ):
            raise ModelUnavailable(
                f"{self.label}: budget ${self.budget_usd:.2f} reached (estimated spend "
                f"${self.spent_usd:.3f}, last call ${self.last_call_usd:.3f}); stopping so the "
                "next call cannot go over"
            )
        attempt = 0
        empties = 0
        while True:
            self._space_out()
            self.calls += 1
            try:
                reply = self.inner.generate(system, prompt, settings)
                self.last_call_usd = reply.latency_s * self.usd_per_second
                self.spent_usd += self.last_call_usd
                # A reply with no text at all (for example a provider that ends the turn
                # with finish_reason=tool_calls although no tool was offered) is an API
                # quirk, not an answer. Ask again a bounded number of times and record it.
                why = reply.raw_meta.get("finish_reason") or reply.raw_meta.get("stop_reason")
                # Out of tokens is the model's own behaviour (it kept reasoning), and asking
                # again with the same budget repeats it, so that case is not retried.
                if (not reply.text.strip() and empties < self.max_empty_retries
                        and why not in TOKEN_LIMIT_REASONS):
                    empties += 1
                    self.notify(f"[{self.label}] empty reply (finish_reason={why}); asking "
                                f"again ({empties}/{self.max_empty_retries})")
                    continue
                reply.raw_meta["empty_retries"] = empties
                return reply
            except Exception as exc:  # noqa: BLE001 - provider SDKs raise many types
                if is_request_too_large(exc):
                    raise RequestTooLarge(
                        f"{self.label}: request exceeds the provider's per-request token limit "
                        f"({str(exc)[:200]})"
                    ) from exc
                if is_daily_quota(exc):
                    raise ModelUnavailable(f"{self.label}: daily quota exhausted ({exc})") from exc
                if not is_retryable(exc) or attempt >= self.max_retries:
                    raise ModelUnavailable(
                        f"{self.label}: giving up after {attempt} retries: "
                        f"{type(exc).__name__}: {exc}"
                    ) from exc
                delay = _retry_after(exc)
                if delay is None:
                    said = retry_in_message(exc)  # provider told us how long to wait
                    delay = (
                        min(self.max_delay_s * 2, said + 1.0)
                        if said is not None
                        else min(self.max_delay_s, self.base_delay_s * (2 ** attempt))
                    )
                attempt += 1
                self.retries += 1
                self.notify(f"[{self.label}] {type(exc).__name__} (HTTP {_status(exc) or '?'}); "
                            f"retry {attempt}/{self.max_retries} in {delay:.0f}s")
                self._sleep(delay)


def wrap_for_model(inner: Any, m: dict[str, Any], spent_usd: float = 0.0) -> RateLimitedAdapter:
    """Build the wrapper from a [[model]] entry (rpm, rpd, max_retries are optional).

    budget_usd caps estimated spend on a pay-per-compute host: each call is
    charged latency_s * usd_per_second, and the run stops before a call that the
    last call's cost suggests would go over. spent_usd is the spend already
    recorded by earlier runs, so the cap holds across resumes.
    """
    budget = m.get("budget_usd")
    if budget is not None and not m.get("usd_per_second"):
        raise ValueError(f"{m.get('label')}: budget_usd needs usd_per_second")
    return RateLimitedAdapter(
        inner,
        label=m.get("label", "model"),
        rpm=m.get("rpm"),
        rpd=m.get("rpd"),
        max_retries=int(m.get("max_retries", 6)),
        budget_usd=float(budget) if budget is not None else None,
        usd_per_second=float(m.get("usd_per_second", 0.0)),
        spent_usd=spent_usd,
    )
