"""Shared helpers for Python anti-pattern checker tests."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[6]


def checker_with_sample_run(
    *,
    checker_relpath: str,
    src: str,
    filename: str = "sample.py",
    extra_args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    """Write a temporary Python sample and run one checker against it.

    Args:
        checker_relpath: Provider-repository-relative checker path.
        src: Python source to analyze.
        filename: Sample filename within the temporary scope.
        extra_args: Additional checker arguments.

    Returns:
        Completed checker process.
    """

    temp_root = Path("/tmp/pytest_project_standard_checks")
    temp_root.mkdir(parents=True, exist_ok=True)
    sample_dir = Path(tempfile.mkdtemp(prefix="sample-", dir=temp_root))
    sample_path = sample_dir / filename
    sample_path.write_text(src, encoding="utf-8")
    try:
        return subprocess.run(
            [checker_relpath, str(sample_path), *extra_args],
            capture_output=True,
            check=False,
            cwd=ROOT,
            text=True,
        )
    finally:
        shutil.rmtree(sample_dir, ignore_errors=True)
        try:
            temp_root.rmdir()
        except OSError:
            pass
