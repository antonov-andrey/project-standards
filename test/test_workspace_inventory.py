"""Behavior tests for the read-only workspace standard inventory."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = (
    ROOT / "plugins" / "project-standards" / "skills" / "project-standard-audit" / "scripts" / "workspace_inventory.py"
)


def _git_init(project_path: Path) -> None:
    """Initialize one deterministic Git worktree.

    Args:
        project_path: New project directory.
    """

    project_path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(project_path)], check=True)
    subprocess.run(["git", "-C", str(project_path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(project_path), "config", "user.name", "Test"], check=True)


def _available_standard_name_list_get() -> list[str]:
    """Return the provider catalog used by the real inventory command.

    Returns:
        Sorted provider capability names.
    """

    skill_root = ROOT / "plugins" / "project-standards" / "skills"
    return sorted(path.name for path in skill_root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file())


def _instruction_text_get(*, extra_standard: str = "", omitted_standard: str = "") -> str:
    """Return one mechanically valid root instruction document.

    Args:
        extra_standard: Optional additional provider capability name.
        omitted_standard: Optional provider capability omitted from the catalog.

    Returns:
        Complete instruction text.
    """

    standard_name_list = [
        standard_name for standard_name in _available_standard_name_list_get() if standard_name != omitted_standard
    ]
    if extra_standard:
        standard_name_list.append(extra_standard)
    standard_line_list = [f"- `project-standards:{standard_name}`\n" for standard_name in sorted(standard_name_list)]
    return (
        "# Repository Guidelines\n\n"
        "## Table Of Contents\n\n"
        "- [Required Standards](#required-standards)\n\n"
        "## Required Standards\n\n"
        f"{''.join(standard_line_list)}"
    )


def _project_write(project_path: Path, *, extra_standard: str = "", omitted_standard: str = "") -> None:
    """Write the exact mechanically required project metadata.

    Args:
        project_path: Initialized project worktree.
        extra_standard: Optional additional provider capability name.
        omitted_standard: Optional provider capability omitted from the catalog.
    """

    (project_path / "AGENTS.md").write_text(
        _instruction_text_get(extra_standard=extra_standard, omitted_standard=omitted_standard),
        encoding="utf-8",
    )


def _tool_run(workspace_root: Path) -> subprocess.CompletedProcess[str]:
    """Run the real inventory tool for one workspace.

    Args:
        workspace_root: Explicit workspace directory.

    Returns:
        Completed tool subprocess.
    """

    return subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            "--workspace-root",
            str(workspace_root),
            "--check",
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def test_check_reports_clean_complete_catalog_without_semantic_verdict(tmp_path: Path) -> None:
    """A complete provider catalog reports clean mechanics and mandatory semantic audit.

    Args:
        tmp_path: Pytest temporary directory.
    """

    workspace_root = tmp_path / "workspace"
    project_path = workspace_root / "project"
    _git_init(project_path)
    _project_write(project_path)

    result = _tool_run(workspace_root)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    available_standard_name_list = _available_standard_name_list_get()
    assert payload["available_project_standard_list"] == available_standard_name_list
    assert payload["mechanical_status"] == "clean"
    assert payload["semantic_audit_required"] is True
    assert "is_valid" not in payload
    project_payload = payload["project_list"][0]
    assert project_payload["declared_project_standard_list"] == available_standard_name_list
    assert project_payload["mechanical_status"] == "clean"
    assert project_payload["missing_project_standard_list"] == []
    assert project_payload["semantic_audit_required"] is True
    assert "required_standard_list" not in project_payload


def test_check_reports_exact_catalog_findings(tmp_path: Path) -> None:
    """Every catalog metadata failure is reported without inference.

    Args:
        tmp_path: Pytest temporary directory.
    """

    workspace_root = tmp_path / "workspace"
    project_path = workspace_root / "project"
    _git_init(project_path)
    _project_write(
        project_path,
        extra_standard="unavailable-standard",
        omitted_standard="python-developer",
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["mechanical_status"] == "finding"
    project_payload = payload["project_list"][0]
    assert project_payload["missing_project_standard_list"] == ["python-developer"]
    assert project_payload["missing_root_instruction_list"] == []
    assert project_payload["unavailable_project_standard_list"] == ["unavailable-standard"]


def test_check_reports_missing_root_instruction_file(tmp_path: Path) -> None:
    """A missing root instruction file is one exact mechanical finding.

    Args:
        tmp_path: Pytest temporary directory.
    """

    workspace_root = tmp_path / "workspace"
    project_path = workspace_root / "project"
    _git_init(project_path)

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    project_payload = json.loads(result.stdout)["project_list"][0]
    assert project_payload["missing_project_standard_list"] == _available_standard_name_list_get()
    assert project_payload["missing_root_instruction_list"] == ["AGENTS.md"]


def test_check_reports_duplicate_git_common_directory_worktrees_as_inventory(tmp_path: Path) -> None:
    """Two worktrees are reported without treating their existence as a defect.

    Args:
        tmp_path: Pytest temporary directory.
    """

    workspace_root = tmp_path / "workspace"
    project_path = workspace_root / "project"
    worktree_path = workspace_root / "project-worktree"
    _git_init(project_path)
    _project_write(project_path)
    subprocess.run(["git", "-C", str(project_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(project_path), "commit", "-qm", "initial"], check=True)
    subprocess.run(["git", "-C", str(project_path), "worktree", "add", "-q", str(worktree_path)], check=True)

    result = _tool_run(workspace_root)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["mechanical_status"] == "clean"
    assert len(payload["duplicate_git_common_dir_list"]) == 1
    assert len(payload["project_list"]) == 2
