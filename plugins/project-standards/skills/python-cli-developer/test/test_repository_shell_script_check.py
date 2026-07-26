"""Behavior tests for the exact repository shell-script checker."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "repository_shell_script_check.py"


def _checker_run(project_root: Path, path_list: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the checker against one synthetic project scope.

    Args:
        project_root: Synthetic project root.
        path_list: Repository-relative paths passed by the runner.

    Returns:
        Completed checker subprocess.
    """

    request = {
        "path_list": path_list,
        "project_root": str(project_root),
        "protocol_version": 1,
        "scope": "all",
    }
    return subprocess.run(
        [sys.executable, str(CHECKER_PATH)],
        capture_output=True,
        check=False,
        input=json.dumps(request),
        text=True,
    )


def test_checker_accepts_scope_without_shell_scripts(tmp_path: Path) -> None:
    """A scope without one current shell-script artifact is clean.

    Args:
        tmp_path: Pytest temporary directory.
    """

    (tmp_path / "tool.py").write_text('"""Tool."""\n', encoding="utf-8")

    result = _checker_run(tmp_path, ["tool.py"])

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_every_current_shell_script(tmp_path: Path) -> None:
    """Every current `.sh` path receives one exact finding.

    Args:
        tmp_path: Pytest temporary directory.
    """

    (tmp_path / "deploy").mkdir()
    (tmp_path / "deploy" / "run.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (tmp_path / "missing-target.sh").symlink_to("missing-target")
    (tmp_path / "root.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    result = _checker_run(tmp_path, ["deploy/run.sh", "missing-target.sh", "root.sh"])

    assert result.returncode == 1
    assert [json.loads(line)["path"] for line in result.stdout.splitlines()] == [
        "deploy/run.sh",
        "missing-target.sh",
        "root.sh",
    ]
    assert result.stderr == ""
