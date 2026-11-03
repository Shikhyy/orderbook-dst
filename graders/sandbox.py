"""graders/sandbox.py
Subprocess execution sandbox with isolated filesystem and environment.
See docs/03_ARCHITECTURE.md section 7 and docs/07_GRADER_SPEC.md section 5.
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


def prepare_overlay(
    work_dir: Path,
    target_files: dict[str, str],
    alt_reference_dir: Optional[Path] = None,
) -> None:
    """Copy exchange_core into work_dir and overlay candidate target files.

    Rule GRD-05: The grader must overlay only the target files of the task onto the reference.
    """
    ref_dir = alt_reference_dir if alt_reference_dir else (REPO_ROOT / "exchange_core")
    dst_core = work_dir / "exchange_core"
    if dst_core.exists():
        shutil.rmtree(dst_core)
    shutil.copytree(ref_dir, dst_core)

    # Copy any test helpers/conftest
    if (REPO_ROOT / "conftest.py").exists():
        shutil.copy2(REPO_ROOT / "conftest.py", work_dir / "conftest.py")

    # Overlay candidate files
    for rel_path, content in target_files.items():
        dst_path = work_dir / rel_path
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_text(content, encoding="utf-8")


def run_sandboxed(
    command: list[str],
    cwd: Path,
    timeout_s: int = 60,
) -> tuple[int, str, str]:
    """Execute command in an isolated environment using python -I.

    Rule docs/03 section 7:
    - Runs python -I in temporary directory.
    - Strips API keys and credentials from environment.
    - Enforces timeout.
    """
    # Clean environment: preserve only minimal system variables
    clean_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(cwd),
        "PYTHONUNBUFFERED": "1",
    }

    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"TimeoutExpired after {timeout_s}s"
    except Exception as e:
        return -1, "", str(e)


def is_docker_available() -> bool:
    """Check if Docker CLI is installed and the daemon is reachable."""
    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception:
        return False


def run_sandboxed_docker(
    command: list[str],
    cwd: Path,
    timeout_s: int = 60,
    memory_limit: str = "512m",
    cpus: str = "1.0",
    read_only: bool = True,
) -> tuple[int, str, str]:
    """Execute command in an isolated Docker container.

    Security constraints:
    - --network none: strictly prevents any external or local network traffic.
    - -m / --memory: memory limit (default 512MB).
    - --cpus: CPU quota (default 1.0 core).
    - --read-only: root filesystem is read-only (with tmpfs /tmp).
    - Clean environment: no host tokens or API keys mounted.
    """
    if not is_docker_available():
        raise RuntimeError("Docker daemon is not reachable in this environment")

    docker_args = [
        "docker", "run", "--rm",
        "--network", "none",
        "-m", memory_limit,
        f"--cpus={cpus}",
        "-v", f"{cwd.resolve()}:/workspace",
        "-w", "/workspace",
    ]
    if read_only:
        docker_args.extend(["--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])

    # Base image: standard python slim
    docker_args.append("python:3.11-slim")
    docker_args.extend(command)

    try:
        proc = subprocess.run(
            docker_args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"TimeoutExpired after {timeout_s}s in container"
    except Exception as e:
        return -1, "", str(e)
