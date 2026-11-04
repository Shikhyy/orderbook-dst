"""tools/status.py
Show what a model run is doing right now. Safe to run from another terminal.

  python tools/status.py            # one snapshot of results/pilot, results/main, ...
  python tools/status.py --watch    # refresh every 5 s (Ctrl-C to stop)
  python tools/status.py --models models.toml   # expected trials per model

Reads progress.json (a heartbeat the harness writes) and trials.jsonl.
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import tomllib as tomli
except ImportError:  # pragma: no cover
    import tomli  # type: ignore

RUN_DIRS = ["pilot", "main", "feedback", "ablation"]


def _secs(s: Optional[float]) -> str:
    if s is None:
        return "?"
    s = int(max(0, s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h{m:02d}m" if h else (f"{m}m{sec:02d}s" if m else f"{sec}s")


def _alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _bar(done: int, total: int, width: int = 30) -> str:
    frac = done / total if total else 0.0
    fill = int(round(frac * width))
    return "[" + "#" * fill + "." * (width - fill) + f"] {done}/{total} ({frac:.0%})"


def _load_trials(d: Path) -> list[dict[str, Any]]:
    f = d / "trials.jsonl"
    rows: list[dict[str, Any]] = []
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def _expected(models_file: Optional[Path]) -> dict[str, int]:
    if not models_file or not models_file.exists():
        return {}
    cfg = tomli.loads(models_file.read_text(encoding="utf-8")).get("model", [])
    n_tasks = len([d for d in (REPO_ROOT / "tasks").iterdir() if (d / "task.toml").exists()])
    return {m["label"]: (len(m["tasks"]) if m.get("tasks") else n_tasks) * int(m.get("trials", 5))
            for m in cfg}


def snapshot(d: Path, expected: dict[str, int]) -> str:
    rows = _load_trials(d)
    prog_file = d / "progress.json"
    prog: dict[str, Any] = {}
    if prog_file.exists():
        try:
            prog = json.loads(prog_file.read_text(encoding="utf-8"))
        except ValueError:
            pass
    if not rows and not prog:
        return ""
    now = time.time()
    out = [f"=== results/{d.name} " + "=" * 50]

    alive = _alive(prog.get("pid"))
    state = prog.get("state")
    if prog:
        if alive and state == "running":
            out.append(f"State: RUNNING (pid {prog['pid']}), heartbeat "
                       f"{_secs(now - prog.get('updated', now))} ago")
        elif state == "finished":
            out.append("State: finished")
        else:
            out.append("State: NOT RUNNING (stopped or interrupted); "
                       "run the same command again to resume")
        out.append(_bar(prog.get("done", 0), prog.get("total", 0))
                   + (f"  ETA ~{_secs(prog.get('eta_seconds'))}"
                      if alive and prog.get("eta_seconds") is not None else ""))
        cur = prog.get("current") or {}
        if cur:
            out.append(f"Now: {cur.get('model')} | {cur.get('task')} | trial "
                       f"{cur.get('trial')}/{cur.get('trials')}: {cur.get('state')} "
                       f"(for {_secs(now - cur.get('since', now))})")
        for s in prog.get("stopped", []):
            out.append(f"Stopped early: {s}")
        for s in prog.get("skipped", []):
            out.append(f"Skipped (not a model failure): {s}")
    else:
        out.append("State: no heartbeat file (run started before progress tracking); "
                   f"{len(rows)} trials recorded")

    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)
    if by_model:
        out.append("")
        out.append(f"{'model':<18} {'done':>9} {'passed':>7} {'mean score':>11} {'errors':>7}")
        for model, rs in sorted(by_model.items()):
            exp = (prog.get("expected") or {}).get(model) or expected.get(model)
            done = f"{len(rs)}/{exp}" if exp else str(len(rs))
            passed = sum(1 for r in rs if r.get("passed"))
            mean = sum(float(r.get("score", 0)) for r in rs) / len(rs)
            errs = sum(1 for r in rs if r.get("error"))
            out.append(f"{model:<18} {done:>9} {passed:>7} {mean:>11.3f} {errs:>7}")
        last = max(rows, key=lambda r: r.get("timestamp", ""))
        out.append(f"\nLast finished trial: {last['model']} | {last['task_id']} | "
                   f"score {last['score']:.2f} at {last.get('timestamp', '')[11:19]} UTC")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--dir", action="append", help="Run directory (repeatable)")
    ap.add_argument("--models", default=str(REPO_ROOT / "models.toml"))
    ap.add_argument("--watch", action="store_true", help="Refresh every 5 seconds")
    args = ap.parse_args()
    dirs = [Path(p) for p in args.dir] if args.dir else [
        REPO_ROOT / "results" / n for n in RUN_DIRS]
    expected = _expected(Path(args.models))
    while True:
        text = "\n\n".join(s for s in (snapshot(d, expected) for d in dirs if d.exists()) if s)
        if args.watch:
            print("\033[2J\033[H", end="")
        print(text or "No runs found under results/. Start one with `make pilot` or `make run`.")
        if not args.watch:
            return
        print(f"\n(refreshing every 5 s, {time.strftime('%H:%M:%S')}; Ctrl-C to stop)")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            return


if __name__ == "__main__":
    main()
