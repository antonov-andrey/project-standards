"""Behavior tests for provider-owned proxy-wrapper checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_proxy_wrapper_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run the real proxy-wrapper checker against synthetic Python.

    Args:
        project_root: Synthetic Git repository root.
        source: Python source under test.

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


def test_checker_reports_direct_top_level_forwarder(tmp_path: Path) -> None:
    """A docstring plus one unchanged returned call is rejected.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "def proxy(value: str, *, limit: int) -> str:\n"
            '    """Forward without behavior."""\n'
            "    return owner.run(value, limit=limit)\n"
        ),
    )

    assert result.returncode == 1
    assert "trivial top-level proxy wrapper for owner.run()" in json.loads(result.stdout)["message"]
    assert result.stderr == ""


def test_checker_allows_transformation_multiple_steps_and_indirect_targets(tmp_path: Path) -> None:
    """Real transformation, multiple behavior steps, and dynamic targets pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "def transform(value: str) -> str:\n"
            "    return owner.run(value.strip())\n\n"
            "def orchestrate(value: str) -> str:\n"
            "    prepared = value.strip()\n"
            "    return owner.run(prepared)\n\n"
            "def dynamic(value: str) -> str:\n"
            "    return owner.client.run(value)\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
