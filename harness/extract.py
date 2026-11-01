"""harness/extract.py
Code extractor from model replies for OrderBook-DST harness.
See docs/08_HARNESS_AND_STATS.md section 4.
"""
import re
from typing import Optional

# Regex pattern matching:
# ### FILE: <path>
# ```[python]
# <code>
# ```
FILE_BLOCK_REGEX = re.compile(
    r"###\s*FILE:\s*([^\n\r]+?)\s*\n```(?:python)?\s*\n(.*?)\n```",
    re.DOTALL | re.MULTILINE,
)


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

    matches = FILE_BLOCK_REGEX.findall(reply_text)
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
