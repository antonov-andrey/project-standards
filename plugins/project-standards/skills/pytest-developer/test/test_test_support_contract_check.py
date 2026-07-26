"""Behavior tests for root test support and import contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "test_support_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_list: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the real checker process against one synthetic repository.

    Args:
        project_root: Exact synthetic repository root.
        relative_path_list: Current repository-relative path list.

    Returns:
        Completed checker process.
    """

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
                "path_list": sorted(relative_path_list),
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_accepts_test_lib_import_and_conftest_fixture_hook_and_private_helper(tmp_path: Path) -> None:
    """Canonical shared imports and every allowed conftest symbol shape pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    (project_root / "test" / "lib").mkdir(parents=True)
    (project_root / "test" / "lib" / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project_root / "test" / "test_sample.py").write_text(
        "from test.lib.helper import VALUE\n\ndef test_sample():\n    assert VALUE == 1\n",
        encoding="utf-8",
    )
    (project_root / "conftest.py").write_text(
        (
            "import pytest\n\n"
            "@pytest.fixture\n"
            "def sample():\n"
            "    return 1\n\n"
            "def pytest_configure(config):\n"
            "    pass\n\n"
            "def _helper():\n"
            "    pass\n"
        ),
        encoding="utf-8",
    )

    result = _checker_run(
        project_root,
        ["conftest.py", "test/lib/helper.py", "test/test_sample.py"],
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_forbidden_import_conftest_symbols_and_code_support_file(tmp_path: Path) -> None:
    """Every primary test-support violation reports its exact source path.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    (project_root / "test" / "code").mkdir(parents=True)
    (project_root / "test" / "other").mkdir()
    (project_root / "test" / "other" / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project_root / "test" / "test_sample.py").write_text(
        "from test.other.helper import VALUE\n",
        encoding="utf-8",
    )
    (project_root / "test" / "code" / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project_root / "conftest.py").write_text(
        "class PublicSupport:\n    pass\n\ndef helper():\n    pass\n",
        encoding="utf-8",
    )

    result = _checker_run(
        project_root,
        [
            "conftest.py",
            "test/code/helper.py",
            "test/other/helper.py",
            "test/test_sample.py",
        ],
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert finding_list == [
        {
            "line": 1,
            "message": "public class PublicSupport is forbidden in conftest.py",
            "path": "conftest.py",
        },
        {
            "line": 4,
            "message": "public function helper is not a pytest hook or fixture",
            "path": "conftest.py",
        },
        {
            "message": "root test/code/** may contain only code-test modules named test_*.py",
            "path": "test/code/helper.py",
        },
        {
            "line": 1,
            "message": (
                "forbidden root test import from test.other.helper; "
                "shared imported test helpers must live under test/lib/**"
            ),
            "path": "test/test_sample.py",
        },
    ]
    assert result.stderr == ""
