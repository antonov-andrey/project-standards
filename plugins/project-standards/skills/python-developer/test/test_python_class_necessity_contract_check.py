"""Behavior tests for provider-owned class-necessity checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_class_necessity_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run the real class-necessity checker against synthetic Python.

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


def test_checker_reports_namespace_only_class(tmp_path: Path) -> None:
    """A class containing only static helper methods is rejected.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "class Helpers:\n"
            '    """Group detached helper behavior."""\n\n'
            "    @staticmethod\n"
            "    def format(value: str) -> str:\n"
            '        """Return formatted text."""\n'
            "        return value.strip()\n"
        ),
    )

    assert result.returncode == 1
    assert "namespace-only class" in json.loads(result.stdout)["message"]
    assert result.stderr == ""


def test_checker_allows_stateful_inherited_and_framework_decorated_classes(tmp_path: Path) -> None:
    """Instance state, inheritance, and class decorators avoid the certain anti-pattern.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "def register(cls):\n"
            "    return cls\n\n"
            "class Stateful:\n"
            "    def run(self) -> None:\n"
            "        return None\n\n"
            "class Child(Stateful):\n"
            "    @staticmethod\n"
            "    def build() -> str:\n"
            "        return 'x'\n\n"
            "@register\n"
            "class Framework:\n"
            "    @staticmethod\n"
            "    def build() -> str:\n"
            "        return 'x'\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
