"""tools/check_publish.py
Check that every git-tracked file matches at least one pattern in publish_allowlist.txt.
Exit 1 if any file is not in the allowlist. Exit 0 if all files are allowed.
"""
import fnmatch
import subprocess
import sys
from pathlib import Path

ALLOWLIST = Path(__file__).parent / "publish_allowlist.txt"


def load_patterns() -> list[str]:
    """Load non-comment, non-empty lines from the allowlist."""
    patterns: list[str] = []
    for line in ALLOWLIST.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def get_tracked_files() -> list[str]:
    """Return the list of files tracked by git."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [p for p in result.stdout.splitlines() if p]


def is_allowed(path: str, patterns: list[str]) -> bool:
    """Return True if the path matches at least one allowlist pattern."""
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
        # Also match the basename for simple patterns.
        if "/" not in pat and fnmatch.fnmatch(Path(path).name, pat):
            return True
    return False


def main() -> int:
    patterns = load_patterns()
    files = get_tracked_files()
    blocked: list[str] = []
    for f in files:
        if not is_allowed(f, patterns):
            blocked.append(f)
    if blocked:
        print("check-publish: FAIL")
        for f in blocked:
            print(f"  not in allowlist: {f}")
        return 1
    print("check-publish: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
