"""Behavior tests for provider-owned Python visibility checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_visibility_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_by_source_map: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the real visibility checker against synthetic modules.

    Args:
        project_root: Synthetic Git repository root.
        relative_path_by_source_map: Python source keyed by repository path.

    Returns:
        Completed checker process.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project_root, check=True)
    for relative_path, source in relative_path_by_source_map.items():
        path = project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
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
                "path_list": sorted(relative_path_by_source_map),
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_accepts_private_local_and_public_cross_module_symbols(tmp_path: Path) -> None:
    """Visibility matches local and cross-module use boundaries.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/demo/source.py": (
                '"""Synthetic source."""\n\n'
                "def _local() -> str:\n"
                "    return 'x'\n\n"
                "def public_value_get() -> str:\n"
                "    return _local()\n"
            ),
            "lib/demo/use.py": (
                '"""Synthetic use."""\n\n'
                "from lib.demo.source import public_value_get\n\n"
                "VALUE = public_value_get()\n"
            ),
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_private_class_public_local_function_and_cross_module_private_use(tmp_path: Path) -> None:
    """All primary visibility violations report their defining paths and lines.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/demo/source.py": (
                '"""Synthetic source."""\n\n'
                "class _Hidden:\n"
                "    pass\n\n"
                "def public_local() -> str:\n"
                "    return 'x'\n\n"
                "def _shared() -> str:\n"
                "    return public_local()\n"
            ),
            "lib/demo/use.py": '"""Synthetic use."""\n\nfrom lib.demo.source import _shared\n\nVALUE = _shared()\n',
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert {finding["path"] for finding in finding_list} == {"lib/demo/source.py"}
    assert {finding["line"] for finding in finding_list} == {3, 6, 9}
    assert any("private top-level class _Hidden" in finding["message"] for finding in finding_list)
    assert any("public function public_local" in finding["message"] for finding in finding_list)
    assert any("private function _shared is used by other modules" in finding["message"] for finding in finding_list)
    assert result.stderr == ""
