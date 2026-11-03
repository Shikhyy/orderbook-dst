#!/usr/bin/env python3
"""tools/check_commit_msg.py
Validate commit message against Conventional Commits and docs/17.

Rules:
1. Format: type(scope): subject or type: subject
2. Allowed types: feat, fix, docs, test, refactor, perf, build, ci, chore, revert
3. First line (subject line) <= 72 characters
"""
import re
import sys

ALLOWED_TYPES = {
    "feat",
    "fix",
    "docs",
    "test",
    "refactor",
    "perf",
    "build",
    "ci",
    "chore",
    "revert",
}

COMMIT_PATTERN = re.compile(
    r"^(?P<type>[a-zA-Z0-9_-]+)(?:\((?P<scope>[a-zA-Z0-9_/-]+)\))?:\s+(?P<subject>.+)$"
)


def validate_commit_message(msg: str) -> tuple[bool, str]:
    lines = msg.strip().splitlines()
    if not lines:
        return False, "Commit message cannot be empty."

    first_line = lines[0].strip()
    if len(first_line) > 72:
        return (
            False,
            f"Commit subject line exceeds 72 characters ({len(first_line)} chars):\n'{first_line}'",
        )

    match = COMMIT_PATTERN.match(first_line)
    if not match:
        msg = f"Commit message does not match Conventional Commits:\n'{first_line}'"
        return False, msg

    commit_type = match.group("type")
    if commit_type not in ALLOWED_TYPES:
        types_str = ", ".join(sorted(ALLOWED_TYPES))
        msg = f"Disallowed commit type '{commit_type}'. Allowed: {types_str}"
        return False, msg

    return True, "OK"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: check_commit_msg.py <commit_msg_file_or_text>", file=sys.stderr)
        return 1

    arg = sys.argv[1]
    # Check if arg is a path to a file
    try:
        with open(arg, "r", encoding="utf-8") as f:
            content = f.read()
    except (FileNotFoundError, OSError):
        content = arg

    valid, reason = validate_commit_message(content)
    if not valid:
        print(f"ERROR: Invalid commit message:\n{reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
