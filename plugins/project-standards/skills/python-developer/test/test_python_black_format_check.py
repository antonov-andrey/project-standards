"""Behavior tests for the provider-owned Black formatting checker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_black_format_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run the real checker against one synthetic repository.

    Args:
        project_root: Synthetic Git repository root.
        source: Python source to check.

    Returns:
        Completed checker process.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project_root, check=True)
    (project_root / "module.py").write_text(source, encoding="utf-8")
    environment_map = os.environ.copy()
    environment_map["PYTHONPATH"] = str(PACKAGE_ROOT)
    return subprocess.run(
        [sys.executable, str(CHECKER_PATH)],
        capture_output=True,
        check=False,
        cwd=project_root,
        env=environment_map,
        input=json.dumps(
            {
                "path_list": ["module.py"],
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_accepts_canonical_black_output(tmp_path: Path) -> None:
    """Canonical Python source produces no finding.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(tmp_path, '"""Describe the module."""\n\nVALUE = [1, 2, 3]\n')

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_noncanonical_black_output_without_mutation(tmp_path: Path) -> None:
    """Noncanonical source reports its path and remains unchanged.

    Args:
        tmp_path: Pytest temporary directory.
    """

    source = '"""Describe the module."""\n\nVALUE=[1,2,3]\n'
    result = _checker_run(tmp_path, source)

    assert result.returncode == 1
    assert [json.loads(line) for line in result.stdout.splitlines()] == [
        {
            "message": "file differs from Black --target-version py314 --line-length 120",
            "path": "module.py",
        }
    ]
    assert (tmp_path / "module.py").read_text(encoding="utf-8") == source
    assert result.stderr == ""
