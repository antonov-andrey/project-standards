"""Behavior tests for the project documentation checker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "documentation_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, path_list: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the real checker process against one isolated repository tree.

    Args:
        project_root: Isolated target root.
        path_list: Manifest-selected current paths.

    Returns:
        Completed checker process.
    """

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PACKAGE_ROOT)
    return subprocess.run(
        [sys.executable, str(CHECKER_PATH)],
        capture_output=True,
        check=False,
        cwd=project_root,
        env=environment,
        input=json.dumps(
            {
                "path_list": sorted(path_list),
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_accepts_existing_targets_and_ignored_link_forms(tmp_path: Path) -> None:
    """Existing, fenced, fragment, and external targets produce no findings.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    (project_root / "docs").mkdir(parents=True)
    (project_root / "target.md").write_text("# Target\n", encoding="utf-8")
    (project_root / "docs" / "guide.md").write_text(
        (
            "[target](../target.md?raw=1#section)\n"
            "[fragment](#local)\n"
            "[external](https://example.test/missing)\n"
            "```\n"
            "[fixture](missing.md)\n"
            "```\n"
        ),
        encoding="utf-8",
    )

    result = _checker_run(project_root, ["docs/guide.md", "target.md"])

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_broken_target_with_document_line(tmp_path: Path) -> None:
    """One missing local target reports its exact document and line.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    (project_root / "docs").mkdir(parents=True)
    (project_root / "docs" / "guide.md").write_text(
        "# Guide\n\n[missing](missing.md)\n",
        encoding="utf-8",
    )

    result = _checker_run(project_root, ["docs/guide.md"])

    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "line": 3,
        "message": "broken repository-local Markdown target: 'missing.md'",
        "path": "docs/guide.md",
    }
    assert result.stderr == ""


def test_checker_reports_incomplete_and_unsorted_existing_script_catalog(tmp_path: Path) -> None:
    """An existing catalog must sort and exactly cover root Product entrypoints.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    (project_root / "docs").mkdir(parents=True)
    (project_root / "script" / "alpha").mkdir(parents=True)
    (project_root / "script" / "alpha" / "entrypoint.py").write_text("", encoding="utf-8")
    (project_root / "script" / "beta").mkdir(parents=True)
    (project_root / "script" / "beta" / "entrypoint.py").write_text("", encoding="utf-8")
    (project_root / "alpha.py").write_text("", encoding="utf-8")
    (project_root / "beta.py").write_text("", encoding="utf-8")
    (project_root / "docs" / "script_catalog.md").write_text(
        "# Scripts\n\n## Каталог Скриптов\n\n- `beta.py` - beta\n- `alpha.py` - alpha\n",
        encoding="utf-8",
    )

    result = _checker_run(
        project_root,
        [
            "alpha.py",
            "beta.py",
            "docs/script_catalog.md",
            "script/alpha/entrypoint.py",
            "script/beta/entrypoint.py",
        ],
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert finding_list == [
        {
            "message": "script catalog entries must be alphabetically sorted",
            "path": "docs/script_catalog.md",
        },
        {
            "message": (
                "script catalog entries must exactly cover Product root entrypoints: "
                "expected ['alpha.py', 'beta.py'], found ['beta.py', 'alpha.py']"
            ),
            "path": "docs/script_catalog.md",
        },
    ]
