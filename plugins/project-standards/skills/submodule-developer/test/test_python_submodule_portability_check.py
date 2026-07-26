"""Behavior tests for direct-submodule Python portability checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "python_submodule_portability_check.py"
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


def _project_create(tmp_path: Path) -> Path:
    """Create one synthetic consumer with a direct submodule declaration.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Synthetic consumer root.
    """

    project_root = tmp_path / "sample-project"
    (project_root / "provider" / "package").mkdir(parents=True)
    (project_root / "provider" / "test").mkdir()
    (project_root / ".gitmodules").write_text(
        '[submodule "provider"]\n\tpath = provider\n\turl = https://example.invalid/provider.git\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", "-b", "main"], check=True, cwd=project_root)
    return project_root


def test_checker_accepts_portable_code_and_excludes_owner_tests(tmp_path: Path) -> None:
    """Portable runtime code passes and test-only fixture values are ignored.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    (project_root / "provider" / "package" / "model.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project_root / "provider" / "test" / "test_model.py").write_text(
        '__database_key__ = "fixture"\n',
        encoding="utf-8",
    )

    result = _checker_run(
        project_root,
        [
            ".gitmodules",
            "provider/package/model.py",
            "provider/test/test_model.py",
        ],
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_every_primary_portability_failure_with_lines(tmp_path: Path) -> None:
    """Project names, DB keys, and absolute user paths are all rejected.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    relative_path = "provider/package/model.py"
    (project_root / relative_path).write_text(
        (
            'PROJECT = "sample-project"\n'
            '__database_key__ = "consumer_database"\n'
            'HOME_PATH = "/home/example/data"\n'
        ),
        encoding="utf-8",
    )

    result = _checker_run(project_root, [".gitmodules", relative_path])

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert finding_list == [
        {
            "line": 1,
            "message": "submodule code hardcodes the consuming project identifier",
            "path": relative_path,
        },
        {
            "line": 2,
            "message": "submodule code hardcodes a database key",
            "path": relative_path,
        },
        {
            "line": 3,
            "message": "submodule code hardcodes an absolute user path",
            "path": relative_path,
        },
    ]
    assert result.stderr == ""
