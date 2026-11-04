"""harness/extract.py
Code extractor from model replies for OrderBook-DST harness.
See docs/08_HARNESS_AND_STATS.md section 4.
"""
import re
from typing import Optional

# Two layouts are accepted, because the instructions have shown both and the code in
# the reply is unambiguous either way. Whichever a model picks must not decide the score.
#
# Layout A (the system message): the marker line, then a fenced block.
#   ### FILE: <path>
#   ```python
#   <code>
#   ```
# Layout B: the marker as the first line inside the fenced block.
#   ```python
#   ### FILE: <path>
#   <code>
#   ```
FILE_BLOCK_ABOVE = re.compile(
    r"###[ \t]*FILE:[ \t]*([^\n\r]+?)[ \t]*\n```(?:python)?[ \t]*\n(.*?)\n```",
    re.DOTALL,
)
FILE_BLOCK_INSIDE = re.compile(
    r"```(?:python)?[ \t]*\n[ \t]*###[ \t]*FILE:[ \t]*([^\n\r]+?)[ \t]*\n(.*?)\n```",
    re.DOTALL,
)
FILE_BLOCK_REGEX = FILE_BLOCK_ABOVE  # kept for backwards compatibility


def classify_extract_error(error: Optional[str], stop_reason: Optional[str]) -> Optional[str]:
    """Name an extraction failure after a reply that ended because it ran out of tokens.

    A reasoning model that spends its whole budget thinking returns no answer. That is a
    real, reportable limit (token budget), different from writing the wrong format.
    """
    if error and stop_reason in ("length", "max_tokens"):
        return "OUTPUT_TRUNCATED"
    return error


def find_file_blocks(reply_text: str) -> list[tuple[str, str]]:
    """All (path, code) blocks in reply order, in either accepted layout."""
    found: list[tuple[int, str, str]] = []
    for rx in (FILE_BLOCK_ABOVE, FILE_BLOCK_INSIDE):
        for m in rx.finditer(reply_text):
            found.append((m.start(), m.group(1), m.group(2)))
    found.sort(key=lambda x: x[0])
    return [(path, code) for _, path, code in found]


def extract_files(
    reply_text: str,
    expected_targets: list[str],
) -> tuple[dict[str, str], Optional[str]]:
    """Extract code files from model response.

    Returns:
        (files_dict, error) where error is None, 'FORMAT_ERROR', or 'MISSING_FILE'.
    """
    if not reply_text or not reply_text.strip():
        return {}, "FORMAT_ERROR"

    matches = find_file_blocks(reply_text)
    if not matches:
        return {}, "FORMAT_ERROR"

    extracted: dict[str, str] = {}
    for raw_path, code in matches:
        path = raw_path.strip().strip("`").strip("'").strip('"')
        # Only retain paths matching expected target files
        if path in expected_targets:
            extracted[path] = code.strip() + "\n"

    # Check that all expected target files are present
    missing = [target for target in expected_targets if target not in extracted]
    if missing:
        # If some blocks were found but target is missing
        return extracted, "MISSING_FILE"

    return extracted, None
