"""harness/progress.py
Live progress for long runs on rate-limited APIs.

A run can spend minutes inside one rate-limit wait or retry, so silence looks like a
hang. This module prints a counter line for every trial and writes a heartbeat file
(<out>/progress.json) that `make status` reads from another terminal.
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Optional


def _fmt_secs(s: float) -> str:
    s = int(max(0, s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h{m:02d}m" if h else (f"{m}m{sec:02d}s" if m else f"{sec}s")


class Progress:
    def __init__(
        self,
        out_dir: Path,
        total: int,
        already_done: int = 0,
        mode: str = "single_turn",
        expected: Optional[dict[str, int]] = None,
    ):
        self.path = out_dir / "progress.json"
        self.total = total
        self.done = already_done
        self.start_done = already_done
        self.t0 = time.time()
        self.mode = mode
        self.expected = expected or {}
        self.current: dict[str, Any] = {}
        self.per_model: dict[str, dict[str, int]] = {}
        self.finished_state: Optional[str] = None
        self.stopped: list[str] = []
        self.skipped: list[str] = []
        self._write()

    # -- bookkeeping -----------------------------------------------------------------
    def eta(self) -> Optional[float]:
        new = self.done - self.start_done
        if new <= 0:
            return None
        per = (time.time() - self.t0) / new
        return per * max(0, self.total - self.done)

    def line(self, text: str) -> None:
        eta = self.eta()
        stamp = time.strftime("%H:%M:%S")
        eta_s = f" | ETA ~{_fmt_secs(eta)}" if eta is not None else ""
        print(f"[{stamp}] [{self.done}/{self.total}]{eta_s} {text}", flush=True)

    def start_trial(self, model: str, task: str, trial: int, trials: int) -> None:
        self.current = {"model": model, "task": task, "trial": trial + 1, "trials": trials,
                        "state": "calling model", "since": time.time()}
        self.line(f"{model} | {task} | trial {trial + 1}/{trials}: calling model")
        self._write()

    def set_state(self, state: str) -> None:
        """Called from the rate limiter: waiting, retrying, etc."""
        if self.current:
            self.current["state"] = state
            self.current["since"] = time.time()
        print(f"[{time.strftime('%H:%M:%S')}]   {state}", flush=True)
        self._write()

    def finish_trial(self, model: str, summary: str) -> None:
        self.done += 1
        pm = self.per_model.setdefault(model, {"done": 0})
        pm["done"] += 1
        self.line(f"{model}: {summary}")
        self.current = {}
        self._write()

    def skip_trial(self, model: str, task: str, reason: str, count: int = 1) -> None:
        """A task that cannot be run on this model (for example its prompt is over the
        provider's per-request limit). Counted as handled so the ETA stays sane, and
        listed so it is never mistaken for a model failure."""
        self.done += count
        self.skipped.append(f"{model} | {task}: {reason}")
        self.line(f"SKIPPED {model} | {task}: {reason}")
        self.current = {}
        self._write()

    def model_stopped(self, model: str, reason: str) -> None:
        self.stopped.append(f"{model}: {reason}")
        self.line(f"STOPPED {model}: {reason}")
        self._write()

    def finish_run(self) -> None:
        self.finished_state = "finished"
        self.current = {}
        self.line("run finished")
        self._write()

    def _write(self) -> None:
        data = {
            "pid": os.getpid(),
            "mode": self.mode,
            "started": self.t0,
            "updated": time.time(),
            "total": self.total,
            "done": self.done,
            "eta_seconds": self.eta(),
            "current": self.current,
            "per_model": self.per_model,
            "expected": self.expected,
            "stopped": self.stopped,
            "skipped": self.skipped,
            "state": self.finished_state or "running",
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass  # progress is advisory; never fail a run over it
