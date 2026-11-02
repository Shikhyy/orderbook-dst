"""tools/grade_docker.py
Docker grading mode entry point.
Runs candidate grading inside an isolated container with --network none,
resource limits (memory, CPU), read-only root filesystem, and execution timeout.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from graders.sandbox import is_docker_available, run_sandboxed_docker  # noqa: E402


def main() -> int:
    print("=" * 80)
    print("ORDERBOOK-DST DOCKER GRADING MODE")
    print("=" * 80)

    if not is_docker_available():
        print(
            "SKIP: Docker is not installed or the Docker daemon is not running in this environment."
        )
        print("Please start the Docker daemon to enable containerized grading.")
        return 0

    print("Docker is available. Running isolated container test...")
    # Test network isolation inside container
    test_cmd = [
        "python", "-c",
        (
            "import socket, sys\n"
            "try:\n"
            "    s = socket.create_connection(('8.8.8.8', 53), timeout=2)\n"
            "    print('FAIL: network socket opened successfully')\n"
            "    sys.exit(1)\n"
            "except Exception as e:\n"
            "    print(f'PASS: network blocked as expected ({e})')\n"
            "    sys.exit(0)\n"
        ),
    ]

    ret, stdout, stderr = run_sandboxed_docker(test_cmd, cwd=REPO_ROOT, timeout_s=30)
    print("Container stdout:", stdout.strip())
    if stderr:
        print("Container stderr:", stderr.strip())

    if ret == 0:
        print("Docker sandbox security verification: PASS")
        return 0
    else:
        print(f"Docker sandbox security verification: FAIL (exit code {ret})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
