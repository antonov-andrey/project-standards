"""Clean-environment installation tests for the development tooling distribution."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _checker_asset_source_by_archive_path_map_get() -> dict[str, Path]:
    """Return every canonical checker asset keyed by its wheel archive path.

    Returns:
        Source paths for every manifest and executable checker asset.
    """

    source_by_archive_path_map: dict[str, Path] = {}
    skill_root = PROJECT_ROOT / "plugins" / "project-standards" / "skills"
    for manifest_path in sorted(skill_root.glob("*/checker.toml")):
        owner_root = manifest_path.parent
        archive_root = Path("project_standards") / "checker_assets" / owner_root.name
        for source_path in [manifest_path, *sorted((owner_root / "scripts").rglob("*"))]:
            if not source_path.is_file() or "__pycache__" in source_path.parts:
                continue
            archive_path = (archive_root / source_path.relative_to(owner_root)).as_posix()
            assert archive_path not in source_by_archive_path_map
            source_by_archive_path_map[archive_path] = source_path
    return source_by_archive_path_map


def _command_run(
    argument_list: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one clean-environment distribution command.

    Args:
        argument_list: Complete executable and argument list.
        cwd: Exact process working directory.
        environment: Optional complete process environment.

    Returns:
        Completed text-mode process result.
    """

    return subprocess.run(
        argument_list,
        capture_output=True,
        check=False,
        cwd=cwd,
        env=environment,
        text=True,
    )


def test_distribution_installs_source_identical_checker_assets_and_runs_console(tmp_path: Path) -> None:
    """A clean wheel install runs only packaged library and checker sources.

    Args:
        tmp_path: Pytest temporary directory.
    """

    build_root = tmp_path / "build"
    build_result = _command_run(
        ["uv", "build", "--out-dir", str(build_root)],
        cwd=PROJECT_ROOT,
    )
    assert build_result.returncode == 0, build_result.stderr
    wheel_path_list = sorted(build_root.glob("*.whl"))
    assert len(wheel_path_list) == 1
    wheel_path = wheel_path_list[0]

    source_by_archive_path_map = _checker_asset_source_by_archive_path_map_get()
    with zipfile.ZipFile(wheel_path) as wheel:
        archive_path_set = {
            archive_path
            for archive_path in wheel.namelist()
            if archive_path.startswith("project_standards/checker_assets/")
        }
        assert archive_path_set == set(source_by_archive_path_map)
        for archive_path, source_path in source_by_archive_path_map.items():
            assert wheel.read(archive_path) == source_path.read_bytes()

    environment_root = tmp_path / "environment"
    venv_result = _command_run(
        ["uv", "venv", "--python", sys.executable, str(environment_root)],
        cwd=tmp_path,
    )
    assert venv_result.returncode == 0, venv_result.stderr
    python_path = environment_root / "bin" / "python"
    install_result = _command_run(
        ["uv", "pip", "install", "--python", str(python_path), str(wheel_path)],
        cwd=tmp_path,
    )
    assert install_result.returncode == 0, install_result.stderr

    process_environment = os.environ.copy()
    process_environment.pop("PYTHONPATH", None)
    help_result = _command_run(
        [str(environment_root / "bin" / "project-standard-check"), "--help"],
        cwd=tmp_path,
        environment=process_environment,
    )
    assert help_result.returncode == 0
    assert "--project-root" in help_result.stdout
    assert "--scope {all,changed}" in help_result.stdout
    assert help_result.stderr == ""

    consumer_root = tmp_path / "consumer"
    consumer_root.mkdir()
    (consumer_root / "AGENTS.md").write_text(
        (
            "# Repository Guidelines\n\n"
            "## Required Standards\n\n"
            "- `project-standards:project-foundation` applies to all project work.\n"
        ),
        encoding="utf-8",
    )
    (consumer_root / "module.py").write_text('"""Describe the module."""\n', encoding="utf-8")
    git_result = _command_run(["git", "init", "-q", "-b", "main"], cwd=consumer_root)
    assert git_result.returncode == 0, git_result.stderr
    check_result = _command_run(
        [
            str(environment_root / "bin" / "project-standard-check"),
            "--project-root",
            str(consumer_root),
            "--scope",
            "all",
        ],
        cwd=tmp_path,
        environment=process_environment,
    )
    assert check_result.returncode == 0, check_result.stderr
    assert json.loads(check_result.stdout) == {
        "mechanical_checker_count": 1,
        "mechanical_error_list": [],
        "mechanical_finding_list": [],
        "mechanical_status": "clean",
        "scope": "all",
        "semantic_audit_required": True,
    }
    assert check_result.stderr == ""

    (consumer_root / "run.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    for scope in ["all", "changed"]:
        finding_result = _command_run(
            [
                str(environment_root / "bin" / "project-standard-check"),
                "--project-root",
                str(consumer_root),
                "--scope",
                scope,
            ],
            cwd=tmp_path,
            environment=process_environment,
        )
        assert finding_result.returncode == 1, finding_result.stderr
        assert json.loads(finding_result.stdout) == {
            "mechanical_checker_count": 1,
            "mechanical_error_list": [],
            "mechanical_finding_list": [
                {
                    "id": "project-foundation.repository-shell-script",
                    "message": "project-local .sh paths are forbidden; use one intentionally executable Python script",
                    "owner": "project-standards:project-foundation",
                    "path": "run.sh",
                }
            ],
            "mechanical_status": "finding",
            "scope": scope,
            "semantic_audit_required": True,
        }
        assert finding_result.stderr == ""

    installed_asset_result = _command_run(
        [
            str(python_path),
            "-c",
            (
                "from importlib import metadata;"
                "import json;"
                "print(json.dumps(sorted(str(path) for path in metadata.files('project-standards') "
                "if str(path).startswith('project_standards/checker_assets/'))))"
            ),
        ],
        cwd=tmp_path,
        environment=process_environment,
    )
    assert installed_asset_result.returncode == 0, installed_asset_result.stderr
    assert json.loads(installed_asset_result.stdout) == sorted(source_by_archive_path_map)
