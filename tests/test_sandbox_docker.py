"""tests/test_sandbox_docker.py
Tests for Docker grading sandbox security and network isolation.
"""
from pathlib import Path

import pytest

from graders.sandbox import is_docker_available, run_sandboxed_docker

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_is_docker_available_function():
    """Verify is_docker_available returns a boolean."""
    avail = is_docker_available()
    assert isinstance(avail, bool)


@pytest.mark.skipif(
    not is_docker_available(),
    reason="Docker daemon is not running in this environment",
)
def test_docker_network_socket_fails():
    """A candidate solution that attempts to open a network socket must fail inside Docker."""
    code = (
        "import socket\n"
        "s = socket.create_connection(('8.8.8.8', 53), timeout=2)\n"
    )
    ret, stdout, stderr = run_sandboxed_docker(
        ["python", "-c", code],
        cwd=REPO_ROOT,
        timeout_s=10,
    )
    # The socket connection must fail with non-zero exit code
    assert ret != 0
    err_msg = stderr.lower()
    assert "network is unreachable" in err_msg or "refused" in err_msg or "oserror" in err_msg
