"""tests/test_secrets_in_replies.py
Verify that evaluation result files preserve raw replies and that
tools/secrets_scan.py detects keys or tokens if they appear in replies.
See Milestone M8-prep item 12.
"""
from pathlib import Path
import tempfile
from tools.secrets_scan import scan_file


def test_clean_reply_passes_secrets_scanner():
    """A standard candidate code reply without secrets must pass clean."""
    clean_code = (
        "def compute_taker_fee(volume_before, notional, cfg):\n"
        "    return 5500000\n"
    )
    with tempfile.TemporaryDirectory() as td:
        reply_file = Path(td) / "reply.txt"
        reply_file.write_text(clean_code, encoding="utf-8")
        findings = scan_file(reply_file)
        assert findings == [], f"Expected clean scan, got: {findings}"


def test_secrets_scanner_catches_fake_reply_with_openai_key():
    """A reply containing an OpenAI-style API key must be flagged by secrets_scan."""
    leaked_reply = (
        "Here is the solution:\n"
        "```python\n"
        "# sk-abcdef12345678901234567890\n"
        "def settle_fill(engine, fill):\n"
        "    return []\n"
        "```\n"
    )
    with tempfile.TemporaryDirectory() as td:
        reply_file = Path(td) / "reply.txt"
        reply_file.write_text(leaked_reply, encoding="utf-8")
        findings = scan_file(reply_file)
        assert len(findings) >= 1, "Secrets scan failed to catch OpenAI key pattern in reply"
        assert any("sk-[A-Za-z0-9]{20,}" in f for f in findings)


def test_secrets_scanner_catches_fake_reply_with_anthropic_key():
    """A reply containing an Anthropic-style API key must be flagged by secrets_scan."""
    leaked_reply = (
        "Model output with key:\n"
        "sk-ant-api03-abcdef12345678901234567890-test\n"
    )
    with tempfile.TemporaryDirectory() as td:
        reply_file = Path(td) / "reply.txt"
        reply_file.write_text(leaked_reply, encoding="utf-8")
        findings = scan_file(reply_file)
        assert len(findings) >= 1, "Secrets scan failed to catch Anthropic key pattern in reply"
        assert any("sk-ant-" in f for f in findings)


def test_secrets_scanner_catches_fake_reply_with_token_assignment():
    """A reply containing an api_key or secret token assignment must be flagged."""
    leaked_reply = (
        "config = {'api_key': 'super_secret_auth_token_value_xyz'}\n"
    )
    with tempfile.TemporaryDirectory() as td:
        reply_file = Path(td) / "reply.txt"
        reply_file.write_text(leaked_reply, encoding="utf-8")
        findings = scan_file(reply_file)
        assert len(findings) >= 1, "Secrets scan failed to catch token assignment pattern in reply"
