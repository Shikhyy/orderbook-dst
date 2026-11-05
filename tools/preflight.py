"""tools/preflight.py
Preflight checklist verification before benchmark evaluation runs.
Implements the 7 preflight checks per Milestone M8-prep.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import tomllib as tomli
except ImportError:
    import tomli  # type: ignore

from graders.sandbox import is_docker_available  # noqa: E402

REQUIRED_TASKS = [
    "f1_fee_a", "f1_fee_b", "f2_replace_a", "f2_replace_b",
    "f3_fix_a", "f3_fix_b", "f4_waterfall_b", "f5_basket_b", "f6_match_b", "f7_funding_b",
    "f8_adl_b",
]

ADAPTER_ENV_VARS = {
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "openai_compat": ["OPENAI_BASE_URL"],
    "gemini": ["GEMINI_API_KEY"],
}


def check_hypotheses_committed() -> tuple[bool, str]:
    hyp_file = REPO_ROOT / "HYPOTHESES.md"
    if not hyp_file.exists():
        return False, "HYPOTHESES.md does not exist"

    text = hyp_file.read_text(encoding="utf-8")
    if "AUTHOR TO WRITE" in text or "AI DRAFT" in text:
        return (
            False,
            "HYPOTHESES.md contains 'AUTHOR TO WRITE' or 'AI DRAFT' (pending human author signoff)",
        )

    res = subprocess.run(
        ["git", "log", "-1", "--format=%h (%ad)", "--date=iso", "--", "HYPOTHESES.md"],
        capture_output=True,
        text=True,
    )
    output = res.stdout.strip()
    if res.returncode == 0 and output:
        return True, f"Committed at commit {output}"
    return False, "HYPOTHESES.md is not committed yet in Git history"


def check_task_difficulty_reasons() -> tuple[bool, str]:
    unwritten = []
    unsigned = []
    missing = []
    for tid in REQUIRED_TASKS:
        t_file = REPO_ROOT / "tasks" / tid / "task.toml"
        if not t_file.exists():
            missing.append(tid)
            continue
        try:
            data = tomli.loads(t_file.read_text(encoding="utf-8"))
            reason = data.get("difficulty_reason", "").strip()
            signoff = data.get("author_signoff", False)
            if not reason or reason == "AUTHOR TO WRITE" or reason.startswith("AI DRAFT"):
                unwritten.append(tid)
            if not signoff:
                unsigned.append(tid)
        except Exception:
            missing.append(tid)

    if missing:
        return False, f"Missing task.toml for: {', '.join(missing)}"
    if unsigned:
        return (
            False,
            f"author_signoff is false (pending author review) for: {', '.join(unsigned)}",
        )
    if unwritten:
        return False, f"difficulty_reason pending author completion for: {', '.join(unwritten)}"
    return True, f"All {len(REQUIRED_TASKS)} tasks have signed-off authored difficulty reasons"


def check_expert_review_exists() -> tuple[bool, str]:
    er_file = REPO_ROOT / "EXPERT_REVIEW.md"
    if not er_file.exists():
        return False, "EXPERT_REVIEW.md does not exist"
    text = er_file.read_text(encoding="utf-8")
    missing_sections = [tid for tid in REQUIRED_TASKS if tid not in text]
    if missing_sections:
        return False, f"Missing task sections for: {', '.join(missing_sections)}"
    return True, f"EXPERT_REVIEW.md exists with all {len(REQUIRED_TASKS)} task sections"


def check_models_toml() -> tuple[bool, str]:
    models_file = REPO_ROOT / "models.toml"
    if not models_file.exists():
        return False, "models.toml does not exist (copy models.example.toml to models.toml)"

    # Check Git tracking
    res = subprocess.run(
        ["git", "ls-files", "models.toml"],
        capture_output=True,
        text=True,
    )
    if res.stdout.strip():
        return False, "models.toml is tracked by Git (must remain untracked / excluded)"

    content = models_file.read_text(encoding="utf-8")
    if "FILL_WITH_EXACT_MODEL_ID" in content:
        return False, "models.toml contains placeholder 'FILL_WITH_EXACT_MODEL_ID'"

    return True, "models.toml exists, untracked by Git, and contains valid model IDs"


def check_adapter_env_vars() -> tuple[bool, str]:
    models_file = REPO_ROOT / "models.toml"
    if not models_file.exists():
        return False, "models.toml not found"

    try:
        data = tomli.loads(models_file.read_text(encoding="utf-8"))
        models = data.get("model", [])
    except Exception as e:
        return False, f"Failed to parse models.toml: {e}"

    if not models:
        return False, "No models defined in models.toml"

    var_status = []
    all_set = True
    seen_vars = set()

    for m in models:
        adapter = m.get("adapter", "")
        if m.get("api_key_env"):
            req_vars = [m["api_key_env"]]
        elif adapter == "openai_compat" and "localhost" in str(m.get("base_url", "")):
            req_vars = []  # local server (e.g. Ollama) needs no key
        else:
            req_vars = ADAPTER_ENV_VARS.get(adapter, [f"{adapter.upper()}_API_KEY"])
        for v in req_vars:
            if v in seen_vars:
                continue
            seen_vars.add(v)
            is_set = bool(os.environ.get(v))
            status_str = "set" if is_set else "not set"
            var_status.append(f"{v}: {status_str}")
            if not is_set:
                all_set = False

    details = ", ".join(var_status)
    return all_set, details


def get_python_bin() -> str:
    venv_py = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def check_make_targets() -> tuple[bool, str]:
    py_bin = get_python_bin()
    # Run make validate
    res_val = subprocess.run(
        [py_bin, str(REPO_ROOT / "tools" / "validate_graders.py")],
        capture_output=True,
        text=True,
    )
    if res_val.returncode != 0:
        return False, "make validate failed"

    # Run secrets scan
    res_sec = subprocess.run(
        [py_bin, str(REPO_ROOT / "tools" / "secrets_scan.py")],
        capture_output=True,
        text=True,
    )
    if res_sec.returncode != 0:
        return False, "make secrets-scan failed"

    # Run check publish
    res_pub = subprocess.run(
        [py_bin, str(REPO_ROOT / "tools" / "check_publish.py")],
        capture_output=True,
        text=True,
    )
    if res_pub.returncode != 0:
        return False, "make check-publish failed"

    return True, "make validate, secrets-scan, and check-publish all passed"


def check_docker_available() -> tuple[bool, str]:
    avail = is_docker_available()
    if avail:
        return True, "Docker daemon is running and responsive"
    return False, "Docker daemon is not running or not installed"


def run_preflight() -> bool:
    print("=" * 80)
    print("ORDERBOOK-DST BENCHMARK PREFLIGHT VERIFICATION")
    print("=" * 80)

    checks = [
        ("1. HYPOTHESES.md committed", check_hypotheses_committed),
        ("2. Task difficulty reasons authored", check_task_difficulty_reasons),
        ("3. EXPERT_REVIEW.md sections present", check_expert_review_exists),
        ("4. models.toml configured & untracked", check_models_toml),
        ("5. Adapter environment variables set", check_adapter_env_vars),
        ("6. Graders, secrets, and publish clean", check_make_targets),
        ("7. Docker sandbox operational", check_docker_available),
    ]

    all_ok = True
    for label, fn in checks:
        ok, detail = fn()
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {label:<40} -> {detail}")
        if not ok:
            all_ok = False

    print("=" * 80)
    if all_ok:
        print("PREFLIGHT RESULT: ALL CHECKS PASSED (Ready for pilot runs)")
    else:
        print("PREFLIGHT RESULT: CHECKS INCOMPLETE (Resolve FAIL items before model runs)")
    print("=" * 80)
    return all_ok


def main() -> int:
    ok = run_preflight()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
