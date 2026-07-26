"""Behavior tests for provider-owned signature-union checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_signature_union_contract_check.py"
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


def test_checker_accepts_single_and_optional_signature_types(tmp_path: Path) -> None:
    """One concrete type and T-or-None signatures remain valid.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Describe the module."""\n\n'
            "def value_get(value: int | None) -> str | None:\n"
            '    """Return text for one optional value."""\n'
            "    return None if value is None else str(value)\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_wide_parameter_and_return_unions(tmp_path: Path) -> None:
    """Wide unions report the callable, path, and source line.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Describe the module."""\n\n'
            "def value_get(value: int | str) -> int | str | None:\n"
            '    """Return one value."""\n'
            "    return value\n"
        ),
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert {finding["path"] for finding in finding_list} == {"module.py"}
    assert {finding["line"] for finding in finding_list} == {3}
    assert any("parameter value" in finding["message"] for finding in finding_list)
    assert any("return annotation" in finding["message"] for finding in finding_list)
    assert result.stderr == ""
