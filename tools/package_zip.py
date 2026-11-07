"""tools/package_zip.py
Package the benchmark repository into a distributable zip archive.
See docs/09_TEST_PLAN.md section 6 and docs/17_GIT_AND_PUBLISH_POLICY.md.
"""
import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ZIP = REPO_ROOT / "orderbook-dst.zip"


def get_tracked_files() -> list[Path]:
    """Get all git-tracked files in the repository."""
    res = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO_ROOT / p for p in res.stdout.splitlines() if p.strip()]


def get_results_files() -> list[Path]:
    """Find files in results/main/, results/feedback/ and transcripts/ to include."""
    results_files: list[Path] = []
    subs = ["main", "feedback", "claude", "ablation", "grader_analysis"]
    dirs = [REPO_ROOT / "results" / sub for sub in subs]
    dirs.append(REPO_ROOT / "transcripts")
    for name in (
        "human_audit.md",
        "my_verdicts.json",
        "my_verdicts_initial.json",
        "audit_sheet.md",
        "audit_key.json",
    ):
        audit_file = REPO_ROOT / "results" / name
        if audit_file.exists():
            results_files.append(audit_file)
    for dir_path in dirs:
        if dir_path.exists():
            for p in dir_path.rglob("*"):
                if p.is_file() and not p.name.startswith("."):
                    results_files.append(p)
    return results_files


def get_packable_files() -> list[Path]:
    """Get list of files eligible for packaging."""
    files_to_pack = set(get_tracked_files())
    files_to_pack.update(get_results_files())

    valid_files: list[Path] = []
    for f in sorted(files_to_pack):
        rel_path = f.relative_to(REPO_ROOT)
        rel_str = str(rel_path)
        if (
            rel_str.startswith("results/pilot/")
            or "scratch/" in rel_str
            or rel_str.endswith(".env")
        ):
            continue
        if f.exists() and f.is_file():
            valid_files.append(f)
    return valid_files


def list_package_files() -> None:
    """Print all files that would be packaged and their total size."""
    files = get_packable_files()
    total_size = 0
    print(f"Files to package ({len(files)} total):")
    for f in files:
        rel = f.relative_to(REPO_ROOT)
        size = f.stat().st_size
        total_size += size
        print(f"  {size:10d}  {rel}")
    total_mb = total_size / (1024 * 1024)
    print(f"\nTotal files: {len(files)}")
    print(f"Total uncompressed size: {total_size} bytes ({total_mb:.2f} MB)")


def package_repository(output_path: Path = OUTPUT_ZIP) -> Path:
    """Build the zip archive containing tracked files and results."""
    valid_files = get_packable_files()

    packaged_files: list[Path] = []
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in valid_files:
            rel_path = f.relative_to(REPO_ROOT)
            zf.write(f, arcname=str(rel_path))
            packaged_files.append(rel_path)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Packaged {len(packaged_files)} files into {output_path.name} ({size_mb:.2f} MB)")
    if size_mb >= 50:
        print(f"WARNING: Package size {size_mb:.2f} MB exceeds 50 MB limit", file=sys.stderr)
        sys.exit(1)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Package repository or list package files.")
    parser.add_argument("--list", action="store_true", help="List files and total size")
    args = parser.parse_args()

    if args.list:
        list_package_files()
    else:
        package_repository()


if __name__ == "__main__":
    main()
