"""Behavior tests for the provider-owned Python docstring checker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_docstring_contract_check.py"
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
    source_path = project_root / "module.py"
    source_path.write_text(source, encoding="utf-8")
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


def test_checker_accepts_complete_google_style_docstrings(tmp_path: Path) -> None:
    """Complete module, class, and callable docstrings pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Describe the fixture module."""\n\n'
            "class Item:\n"
            '    """Store fixture behavior."""\n\n'
            "    def value_get(self, value: int) -> int:\n"
            '        """Return the supplied value.\\n\\n'
            "        Args:\\n"
            "            value: Supplied integer.\\n\\n"
            "        Returns:\\n"
            "            Supplied integer.\\n"
            '        """\n\n'
            "        return value\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_missing_sections_stale_args_and_blank_line_layout(tmp_path: Path) -> None:
    """Primary presence, section, stale-entry, and spacing failures report.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            "class Item:\n"
            "    def value_get(self, value: int) -> int:\n"
            '        """Return the supplied value.\n'
            "        Args:\n"
            "            stale: Wrong name.\n"
            '        """\n'
            "        return value\n"
        ),
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    message_list = [finding["message"] for finding in finding_list]
    assert "missing module docstring" in message_list
    assert "class Item: missing docstring" in message_list
    assert "def value_get: missing arg doc for 'value'" in message_list
    assert "def value_get: stale arg doc entry 'stale'" in message_list
    assert "def value_get: missing Returns section" in message_list
    assert "def value_get: missing blank line after summary line" in message_list
    assert "def value_get: missing blank line after docstring block" in message_list
    assert all(finding["path"] == "module.py" for finding in finding_list)
    assert all("line" not in finding or finding["line"] > 0 for finding in finding_list)
    assert result.stderr == ""
