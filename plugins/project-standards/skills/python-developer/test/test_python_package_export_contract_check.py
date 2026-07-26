"""Behavior tests for provider-owned Python export checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_package_export_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run the real package-export checker against synthetic Python.

    Args:
        project_root: Synthetic Git repository root.
        source: Python source under test.

    Returns:
        Completed checker process.
    """

    project_root.mkdir(parents=True)
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


def test_checker_accepts_defined_imported_and_lazy_export_names(tmp_path: Path) -> None:
    """Bound and explicitly lazy names form valid declared surfaces.

    Args:
        tmp_path: Pytest temporary directory.
    """

    defined_result = _checker_run(
        tmp_path / "defined",
        (
            '"""Synthetic exports."""\n\n'
            "from pathlib import Path\n\n"
            "class Demo:\n"
            "    pass\n\n"
            '__all__ = ["Demo", "Path"]\n'
        ),
    )
    lazy_result = _checker_run(
        tmp_path / "lazy",
        (
            '"""Synthetic lazy exports."""\n\n'
            "def __getattr__(name: str):\n"
            "    return name\n\n"
            '__all__ = ["Deferred"]\n'
        ),
    )

    assert defined_result.returncode == 0
    assert defined_result.stdout == ""
    assert lazy_result.returncode == 0
    assert lazy_result.stdout == ""


def test_checker_reports_malformed_duplicate_and_missing_exports(tmp_path: Path) -> None:
    """Malformed declarations and unavailable names report with source lines.

    Args:
        tmp_path: Pytest temporary directory.
    """

    malformed_result = _checker_run(
        tmp_path / "malformed",
        '"""Synthetic exports."""\n\n__all__ = build_exports()\n',
    )
    duplicate_result = _checker_run(
        tmp_path / "duplicate",
        '"""Synthetic exports."""\n\nDemo = object()\n__all__ = ["Demo", "Demo", "Missing"]\n',
    )

    assert malformed_result.returncode == 1
    malformed_finding = json.loads(malformed_result.stdout)
    assert malformed_finding["path"] == "module.py"
    assert malformed_finding["line"] == 3
    assert "literal list or tuple" in malformed_finding["message"]
    assert duplicate_result.returncode == 1
    duplicate_finding_list = [json.loads(line) for line in duplicate_result.stdout.splitlines()]
    assert {finding["line"] for finding in duplicate_finding_list} == {4}
    assert any("duplicate names: Demo" in finding["message"] for finding in duplicate_finding_list)
    assert any("not bound by the module: Missing" in finding["message"] for finding in duplicate_finding_list)
    assert malformed_result.stderr == ""
    assert duplicate_result.stderr == ""
