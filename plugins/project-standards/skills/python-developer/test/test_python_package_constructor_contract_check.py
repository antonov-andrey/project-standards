"""Behavior tests for provider-owned package constructor checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_package_constructor_contract_check.py"
)
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_by_source_map: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the real package-constructor checker against synthetic modules.

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


def test_checker_accepts_direct_alternative_constructor_and_instance_owner(tmp_path: Path) -> None:
    """Direct same-class constructors and real instance methods pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/demo/model.py": (
                '"""Synthetic models."""\n\n'
                "class Output:\n"
                "    pass\n\n"
                "class Source:\n"
                "    @classmethod\n"
                '    def from_text(cls, value: str) -> "Source":\n'
                "        return cls()\n\n"
                '    def output_build(self) -> "Output":\n'
                "        return Output()\n"
            )
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_wrong_constructor_and_nested_return_with_path_and_line(tmp_path: Path) -> None:
    """Wrong constructor names and container returns report precisely.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/demo/model.py": (
                '"""Synthetic models."""\n\n'
                "class Demo:\n"
                "    @classmethod\n"
                '    def build(cls) -> "Demo":\n'
                "        return cls()\n\n"
                "    @classmethod\n"
                '    def from_text_list(cls) -> list["Demo"]:\n'
                "        return [cls()]\n"
            )
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert {finding["path"] for finding in finding_list} == {"lib/demo/model.py"}
    assert {finding["line"] for finding in finding_list} == {5, 9}
    assert any("must be named from_* or _from_*" in finding["message"] for finding in finding_list)
    assert any("must return Demo directly" in finding["message"] for finding in finding_list)
    assert result.stderr == ""


def test_checker_reports_top_level_return_and_first_parameter_ownership(tmp_path: Path) -> None:
    """Imported returns and first package-object parameters require real owners.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/demo/output.py": '"""Synthetic output."""\n\nclass Output:\n    pass\n',
            "lib/demo/source.py": '"""Synthetic source."""\n\nclass Source:\n    pass\n',
            "lib/demo/workflow.py": (
                '"""Synthetic workflow."""\n\n'
                "from lib.demo.output import Output\n"
                "from lib.demo.source import Source\n\n"
                "def output_build(source: Source) -> Output:\n"
                "    return Output()\n"
            ),
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert {finding["path"] for finding in finding_list} == {"lib/demo/workflow.py"}
    assert {finding["line"] for finding in finding_list} == {6}
    assert any("returns package-local class lib.demo.output.Output" in finding["message"] for finding in finding_list)
    assert any("first package-local object parameter" in finding["message"] for finding in finding_list)
    assert result.stderr == ""
