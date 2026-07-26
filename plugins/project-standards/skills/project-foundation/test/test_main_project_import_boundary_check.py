"""Behavior tests for provider-owned Main project import-boundary checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "main_project_import_boundary_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_by_source_map: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the real checker against one synthetic project.

    Args:
        project_root: Synthetic Git repository root.
        relative_path_by_source_map: Python sources keyed by repository path.

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


def test_checker_accepts_main_project_and_submodule_dependencies(tmp_path: Path) -> None:
    """Main project code may depend on peer Main project and Submodule code.

    Args:
        tmp_path: Pytest temporary directory.
    """

    (tmp_path / ".gitmodules").write_text(
        '[submodule "shared"]\n\tpath = shared\n\turl = https://example.invalid/shared.git\n',
        encoding="utf-8",
    )
    result = _checker_run(
        tmp_path,
        {
            "backend/api.py": '"""API."""\n\nfrom lib.service import run\nfrom shared.client import Client\n',
            "lib/service.py": '"""Service."""\n\n\ndef run() -> None:\n    """Run."""\n',
            "shared/client.py": '"""Client."""\n\n\nclass Client:\n    """Client."""\n',
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_tool_test_script_and_narrower_lib_dependencies(tmp_path: Path) -> None:
    """Every mechanically forbidden Main project dependency reports.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "app.py": '"""Entrypoint."""\n',
            "backend/api.py": (
                '"""API."""\n\n'
                "from app import main\n"
                "from test.fixture import ITEM\n"
                "from tool.runner import run\n"
            ),
            "lib/service.py": '"""Service."""\n\nfrom script.job import execute\n',
            "script/job.py": '"""Job."""\n\n\ndef execute() -> None:\n    """Execute."""\n',
            "test/fixture.py": '"""Fixture."""\n\nITEM = 1\n',
            "tool/runner.py": '"""Runner."""\n\n\ndef run() -> None:\n    """Run."""\n',
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert {finding["path"] for finding in finding_list} == {"backend/api.py", "lib/service.py"}
    message_text = "\n".join(finding["message"] for finding in finding_list)
    assert "root Python script app" in message_text
    assert "root test module test.fixture" in message_text
    assert "root tool module tool.runner" in message_text
    assert "narrower owner module script.job" in message_text
    assert all(finding["line"] > 0 for finding in finding_list)
    assert result.stderr == ""
