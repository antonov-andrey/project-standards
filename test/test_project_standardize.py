"""Behavior tests for read-only project standard inventory."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = (
    ROOT / "plugins" / "project-standards" / "skills" / "project-standardize" / "scripts" / "project_standardize.py"
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


def _instruction_text_get(*, extra_standard: str = "") -> str:
    """Return one mechanically valid root instruction document.

    Args:
        extra_standard: Optional additional provider capability name.

    Returns:
        Complete instruction text.
    """

    extra_line = f"- `project-standards:{extra_standard}` applies.\n" if extra_standard else ""
    return (
        "# Repository Guidelines\n\n"
        "## Table Of Contents\n\n"
        "- [Required Standards](#required-standards)\n\n"
        "## Required Standards\n\n"
        "- `project-standards:project-foundation` applies.\n"
        "- `project-standards:project-instruction-developer` applies.\n"
        f"{extra_line}"
    )


def _project_write(project_path: Path, *, extra_standard: str = "") -> None:
    """Write the exact mechanically required project metadata.

    Args:
        project_path: Initialized project worktree.
        extra_standard: Optional additional provider capability name.
    """

    (project_path / ".gitignore").write_text(".spec/\n", encoding="utf-8")
    (project_path / "AGENTS.md").write_text(
        _instruction_text_get(extra_standard=extra_standard),
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


def test_check_reports_clean_mechanical_inventory_without_semantic_verdict(tmp_path: Path) -> None:
    """A complete baseline reports clean mechanics and mandatory semantic audit.

    Args:
        tmp_path: Pytest temporary directory.
    """

    workspace_root = tmp_path / "workspace"
    project_path = workspace_root / "project"
    _git_init(project_path)
    _project_write(project_path, extra_standard="python-developer")

    result = _tool_run(workspace_root)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["mechanical_status"] == "clean"
    assert payload["semantic_audit_required"] is True
    assert "is_valid" not in payload
    project_payload = payload["project_list"][0]
    assert project_payload["baseline_missing_project_standard_list"] == []
    assert project_payload["declared_project_standard_list"] == [
        "project-foundation",
        "project-instruction-developer",
        "python-developer",
    ]
    assert project_payload["mechanical_status"] == "clean"
    assert project_payload["semantic_audit_required"] is True
    assert "required_standard_list" not in project_payload
    assert "missing_standard_list" not in project_payload


def test_check_reports_exact_capability_and_task_root_findings(tmp_path: Path) -> None:
    """Every closed mechanical metadata failure is reported without inference.

    Args:
        tmp_path: Pytest temporary directory.
    """

    workspace_root = tmp_path / "workspace"
    project_path = workspace_root / "project"
    _git_init(project_path)
    (project_path / ".gitignore").write_text("tmp/\n", encoding="utf-8")
    (project_path / "AGENTS.md").write_text(
        "# Repository Guidelines\n\n"
        "## Required Standards\n\n"
        "- `project-standards:unavailable-standard` applies.\n",
        encoding="utf-8",
    )
    (project_path / ".spec").mkdir()
    (project_path / ".spec" / "task-spec.md").write_text("# Task\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(project_path), "add", "-f", ".spec/task-spec.md"],
        check=True,
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["mechanical_status"] == "finding"
    project_payload = payload["project_list"][0]
    assert project_payload["baseline_missing_project_standard_list"] == [
        "project-foundation",
        "project-instruction-developer",
    ]
    assert project_payload["missing_root_instruction_list"] == []
    assert project_payload["task_root_issue_list"] == [
        "root .spec directory is not ignored by repository .gitignore",
        "tracked .spec paths: .spec/task-spec.md",
    ]
    assert project_payload["unavailable_project_standard_list"] == ["unavailable-standard"]


def test_check_reports_missing_root_instruction_file(tmp_path: Path) -> None:
    """A missing root instruction file is one exact mechanical finding.

    Args:
        tmp_path: Pytest temporary directory.
    """

    workspace_root = tmp_path / "workspace"
    project_path = workspace_root / "project"
    _git_init(project_path)
    (project_path / ".gitignore").write_text("/.spec/\n", encoding="utf-8")

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    project_payload = json.loads(result.stdout)["project_list"][0]
    assert project_payload["baseline_missing_project_standard_list"] == [
        "project-foundation",
        "project-instruction-developer",
    ]
    assert project_payload["missing_root_instruction_list"] == ["AGENTS.md"]


def test_check_uses_repository_ignore_behavior_instead_of_one_literal_rule(tmp_path: Path) -> None:
    """Equivalent root ignore patterns satisfy the portable task-root contract.

    Args:
        tmp_path: Pytest temporary directory.
    """

    workspace_root = tmp_path / "workspace"
    project_path = workspace_root / "project"
    _git_init(project_path)
    _project_write(project_path)
    (project_path / ".gitignore").write_text("*.spec\n", encoding="utf-8")

    result = _tool_run(workspace_root)

    assert result.returncode == 0
    project_payload = json.loads(result.stdout)["project_list"][0]
    assert project_payload["task_root_issue_list"] == []


def test_check_rejects_non_repository_task_root_ignore_source(tmp_path: Path) -> None:
    """A worktree-local exclude cannot replace the portable repository contract.

    Args:
        tmp_path: Pytest temporary directory.
    """

    workspace_root = tmp_path / "workspace"
    project_path = workspace_root / "project"
    _git_init(project_path)
    (project_path / ".gitignore").write_text("tmp/\n", encoding="utf-8")
    (project_path / ".git" / "info" / "exclude").write_text(".spec/\n", encoding="utf-8")
    (project_path / "AGENTS.md").write_text(_instruction_text_get(), encoding="utf-8")

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    project_payload = json.loads(result.stdout)["project_list"][0]
    assert project_payload["task_root_issue_list"] == [
        "root .spec directory is not ignored by repository .gitignore",
    ]


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
