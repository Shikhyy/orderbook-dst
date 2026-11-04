"""tests/test_harness_extract.py
Unit tests for harness extraction, prompt construction, and adapter interfaces.
See docs/08_HARNESS_AND_STATS.md sections 2, 3, 4, 5.
"""
from harness.adapters.mock import MockAdapter
from harness.extract import extract_files
from harness.prompt import build_prompt_for_task


def test_valid_single_file_extraction() -> None:
    reply = """Here is the solution:

### FILE: exchange_core/rules/replace_rule.py
```python
def decide_replace(order, new_price, new_qty, cfg):
    return True
```
"""
    targets = ["exchange_core/rules/replace_rule.py"]
    files, err = extract_files(reply, targets)
    assert err is None
    assert "exchange_core/rules/replace_rule.py" in files
    assert "def decide_replace" in files["exchange_core/rules/replace_rule.py"]


def test_valid_multiple_files_extraction() -> None:
    reply = """### FILE: f1.py
```python
x = 1
```

### FILE: f2.py
```python
y = 2
```
"""
    targets = ["f1.py", "f2.py"]
    files, err = extract_files(reply, targets)
    assert err is None
    assert files["f1.py"].strip() == "x = 1"
    assert files["f2.py"].strip() == "y = 2"


def test_missing_file_error() -> None:
    reply = """### FILE: f1.py
```python
x = 1
```
"""
    targets = ["f1.py", "f2.py"]
    files, err = extract_files(reply, targets)
    assert err == "MISSING_FILE"
    assert "f1.py" in files
    assert "f2.py" not in files


def test_bad_format_no_file_block() -> None:
    reply = """```python
def decide_replace():
    pass
```"""
    targets = ["exchange_core/rules/replace_rule.py"]
    files, err = extract_files(reply, targets)
    assert err == "FORMAT_ERROR"
    assert len(files) == 0


def test_bad_format_empty_reply() -> None:
    files, err = extract_files("", ["f1.py"])
    assert err == "FORMAT_ERROR"
    assert len(files) == 0

    files2, err2 = extract_files("   \n\t  ", ["f1.py"])
    assert err2 == "FORMAT_ERROR"


def test_extra_text_outside_blocks_ignored() -> None:
    reply = """Hello! Here is the implementation that you requested:

### FILE: target.py
```python
answer = 42
```

I hope this helps! Feel free to ask if you have more questions.
"""
    targets = ["target.py"]
    files, err = extract_files(reply, targets)
    assert err is None
    assert files["target.py"].strip() == "answer = 42"


def test_non_target_file_ignored() -> None:
    reply = """### FILE: rogue.py
```python
import os; os.system("echo hacked")
```

### FILE: target.py
```python
clean = True
```
"""
    targets = ["target.py"]
    files, err = extract_files(reply, targets)
    assert err is None
    assert "rogue.py" not in files
    assert "target.py" in files


def test_prompt_construction() -> None:
    bp = build_prompt_for_task("f2_replace_a")
    assert "You are a senior software engineer" in bp.system
    assert "### FILE: <path>" in bp.system
    assert "f2_replace_a" in bp.user_prompt or "Replace Decision Rule" in bp.user_prompt
    assert "exchange_core/rules/replace_rule.py" in bp.user_prompt
    assert len(bp.prompt_sha256) == 64


def test_mock_adapter_interface() -> None:
    adapter = MockAdapter("### FILE: target.py\n```python\nx = 1\n```")
    reply = adapter.generate("system prompt", "user prompt", {})
    assert reply.input_tokens > 0
    assert reply.output_tokens > 0
    assert reply.latency_s > 0
    assert "target.py" in reply.text


def test_marker_inside_the_fence_is_accepted() -> None:
    reply = "```python\n### FILE: exchange_core/a.py\nX = 1\n```\n"
    files, err = extract_files(reply, ["exchange_core/a.py"])
    assert err is None and files["exchange_core/a.py"] == "X = 1\n"


def test_mixed_layouts_in_one_reply_keep_each_file() -> None:
    reply = (
        "### FILE: exchange_core/a.py\n```python\nA = 1\n```\n\n"
        "```python\n### FILE: exchange_core/b.py\nB = 2\n```\n"
    )
    files, err = extract_files(reply, ["exchange_core/a.py", "exchange_core/b.py"])
    assert err is None
    assert files == {"exchange_core/a.py": "A = 1\n", "exchange_core/b.py": "B = 2\n"}


def test_marker_inside_fence_does_not_leak_into_code() -> None:
    reply = "```python\n### FILE: exchange_core/a.py\nimport os\n```\n"
    files, _ = extract_files(reply, ["exchange_core/a.py"])
    assert "FILE:" not in files["exchange_core/a.py"]
