"""Behavior tests for provider-owned multiline-string checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_multiline_string_contract_check.py"
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


def test_checker_accepts_docstrings_and_module_owned_multiline_strings(tmp_path: Path) -> None:
    """Docstrings and one module constant remain valid.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Describe the module."""\n\n'
            'PAYLOAD = """first\n'
            'second"""\n\n'
            "def payload_get() -> str:\n"
            '    """Return the static payload.\n\n'
            "    Returns:\n"
            "        Static payload.\n"
            '    """\n\n'
            "    return PAYLOAD\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_local_multiline_string_with_path_and_line(tmp_path: Path) -> None:
    """One local multiline payload reports without cache or target mutation.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Describe the module."""\n\n'
            "def payload_get() -> str:\n"
            '    """Return one payload."""\n'
            '    return """first\n'
            'second"""\n'
        ),
    )

    assert result.returncode == 1
    assert [json.loads(line) for line in result.stdout.splitlines()] == [
        {
            "line": 5,
            "message": "multiline triple-quoted string must be one module-level constant or module variable",
            "path": "module.py",
        }
    ]
    assert result.stderr == ""
