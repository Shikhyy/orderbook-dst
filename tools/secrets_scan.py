"""tools/secrets_scan.py
Scan all git-tracked files for secret patterns.
Exit 1 if any pattern matches. Exit 0 if clean.
"""
import re
import subprocess
import sys
from pathlib import Path

# Patterns that indicate a secret or private data.
SECRET_PATTERNS = [
    re.compile(r"(?i)['\"]?(api[_-]?key|secret|password|token)['\"]?\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),          # OpenAI style key
    re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}"),    # Anthropic style key
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----"),
    re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),  # email
]

# Allowed email pattern (no-reply GitHub emails are safe).
ALLOWED_EMAIL = re.compile(r"@users\.noreply\.github\.com")


def get_tracked_files() -> list[Path]:
    """Return the list of files tracked by git."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(p) for p in result.stdout.splitlines() if p]


def scan_file(path: Path) -> list[str]:
    """Return a list of findings for one file."""
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pat in SECRET_PATTERNS:
            m = pat.search(line)
            if m:
                # Allow no-reply GitHub emails.
                if ALLOWED_EMAIL.search(m.group(0)):
                    continue
                findings.append(f"  {path}:{lineno}: {pat.pattern!r}")
    return findings


def main() -> int:
    files = get_tracked_files()
    all_findings: list[str] = []
    for f in files:
        all_findings.extend(scan_file(f))
    if all_findings:
        print("secrets-scan: FAIL")
        for line in all_findings:
            print(line)
        return 1
    print("secrets-scan: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
