"""Behavior tests for provider-owned Python dead-code checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_dead_code_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_by_source_map: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the real dead-code checker against synthetic modules.

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


def test_checker_accepts_production_use_framework_decorator_and_embedded_runtime_call(tmp_path: Path) -> None:
    """Real, framework, and embedded-source uses remain valid.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/demo/source.py": (
                '"""Synthetic source."""\n\n'
                "def field_validator(function):\n"
                "    return function\n\n"
                "@field_validator\n"
                "def framework_value_validate(value: str) -> str:\n"
                "    return value\n\n"
                "def embedded_run() -> None:\n"
                "    return None\n\n"
                "def value_get() -> int:\n"
                "    return 1\n"
            ),
            "script/use/main.py": (
                '"""Synthetic use."""\n\n'
                "from lib.demo.source import value_get\n\n"
                "RUNTIME_SOURCE = 'embedded_run()'\n"
                "VALUE = value_get()\n"
            ),
            "plugins/provider/lib/provider_package/__init__.py": '"""Provider package."""\n',
            "plugins/provider/lib/provider_package/cli.py": (
                '"""Configured boundaries."""\n\n'
                "def main() -> int:\n"
                "    return 0\n\n"
                "def pytest_report_header(config) -> str:\n"
                "    return 'provider'\n"
            ),
            "pyproject.toml": (
                "[project]\n"
                'name = "fixture"\n'
                'version = "0.1.0"\n'
                "\n"
                "[project.scripts]\n"
                'fixture = "provider_package.cli:main"\n'
                "\n"
                "[tool.pytest.ini_options]\n"
                'addopts = "-p provider_package.cli"\n'
            ),
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_dead_and_test_only_functions_and_methods(tmp_path: Path) -> None:
    """Dead and test-only definitions report at exact source lines.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/demo/source.py": (
                '"""Synthetic source."""\n\n'
                "def dead_value_get() -> int:\n"
                "    return 1\n\n"
                "def test_value_get() -> int:\n"
                "    return 2\n\n"
                "class Demo:\n"
                "    def dead_run(self) -> None:\n"
                "        return None\n\n"
                "    def tested_run(self) -> None:\n"
                "        return None\n"
            ),
            "script/use/main.py": (
                '"""Synthetic production use."""\n\n' "from lib.demo.source import Demo\n\n" "DEMO_TYPE = Demo\n"
            ),
            "test/test_source.py": (
                '"""Synthetic tests."""\n\n'
                "from lib.demo.source import Demo, test_value_get\n\n"
                "VALUE = test_value_get()\n"
                "Demo().tested_run()\n"
            ),
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert {finding["path"] for finding in finding_list} == {"lib/demo/source.py"}
    assert {finding["line"] for finding in finding_list} == {3, 6, 10, 13}
    assert any("dead function dead_value_get" in finding["message"] for finding in finding_list)
    assert any("used only in tests function test_value_get" in finding["message"] for finding in finding_list)
    assert any("dead method Demo.dead_run" in finding["message"] for finding in finding_list)
    assert any("used only in tests method Demo.tested_run" in finding["message"] for finding in finding_list)
    assert result.stderr == ""
