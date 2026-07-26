#!/usr/bin/env python3
"""Discover Git projects and report exact mechanical standard metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Sequence, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards import required_standard_name_list_get

STANDARD_SKILL_ROOT = Path(__file__).resolve().parents[2]


def _args_parse() -> argparse.Namespace:
    """Parse the read-only workspace inventory command line.

    Returns:
        Parsed command-line namespace.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_const",
        const=True,
        dest=argparse.SUPPRESS,
        required=True,
        help="Run the read-only mechanical inventory.",
    )
    parser.add_argument(
        "--workspace-root",
        required=True,
        type=Path,
        help="Directory whose immediate children are candidate Git worktrees.",
    )
    return parser.parse_args()


def main() -> int:
    """Print one workspace mechanical inventory and return its status.

    Returns:
        Zero for a clean mechanical result, otherwise one.
    """

    args = _args_parse()
    inventory = ProjectStandardInventory(args.workspace_root.resolve())
    workspace_report = inventory.workspace_report_get()
    inventory.report_print(workspace_report)
    return int(workspace_report["mechanical_status"] != "clean")


class ProjectReport(TypedDict):
    """Store exact mechanical metadata for one discovered project."""

    declared_project_standard_list: list[str]
    git_common_dir: Path
    mechanical_status: str
    missing_project_standard_list: list[str]
    missing_root_instruction_list: list[str]
    path: Path
    task_root_issue_list: list[str]
    unavailable_project_standard_list: list[str]


def _available_standard_set_get() -> set[str]:
    """Return capability names present in this provider installation.

    Returns:
        Available provider capability names.
    """

    return {path.name for path in STANDARD_SKILL_ROOT.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()}


def _git_output_get(project_path: Path, argument_list: Sequence[str]) -> str:
    """Run one read-only Git command.

    Args:
        project_path: Git worktree root.
        argument_list: Arguments passed after ``git``.

    Returns:
        Stripped standard output.
    """

    return subprocess.run(
        ["git", "-C", str(project_path), *argument_list],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


def _missing_root_instruction_list_get(agents_path: Path) -> list[str]:
    """Return exact root instruction file-presence issues.

    Args:
        agents_path: Root project instruction path.

    Returns:
        Missing metadata identifiers.
    """

    return [] if agents_path.is_file() else ["AGENTS.md"]


def _task_root_issue_list_get(project_path: Path) -> list[str]:
    """Return ignored task-root contract issues from actual Git behavior.

    Args:
        project_path: Canonical project worktree root.

    Returns:
        Missing repository ignore behavior or tracked-task identifiers.

    Raises:
        RuntimeError: If Git cannot evaluate the task-root ignore behavior.
    """

    issue_list: list[str] = []
    ignore_result = subprocess.run(
        ["git", "-C", str(project_path), "check-ignore", "--verbose", "--no-index", ".spec/"],
        capture_output=True,
        check=False,
        text=True,
    )
    if ignore_result.returncode > 1:
        raise RuntimeError(ignore_result.stderr.strip() or "Git could not evaluate the root .spec ignore behavior.")
    ignore_source = ignore_result.stdout.partition(":")[0]
    if ignore_result.returncode != 0 or ignore_source != ".gitignore":
        issue_list.append("root .spec directory is not ignored by repository .gitignore")
    tracked_task_path_list = _git_output_get(project_path, ["ls-files", ".spec"]).splitlines()
    if tracked_task_path_list:
        issue_list.append(f"tracked .spec paths: {', '.join(tracked_task_path_list)}")
    return issue_list


class ProjectStandardInventory:
    """Own read-only mechanical inventory for one explicit workspace."""

    def __init__(self, workspace_root: Path) -> None:
        """Initialize one inventory boundary.

        Args:
            workspace_root: Canonical workspace directory.
        """

        if not workspace_root.is_dir():
            raise ValueError(f"Workspace root is not a directory: {workspace_root}")
        self._available_standard_set = _available_standard_set_get()
        self._workspace_root = workspace_root

    def _project_path_list_get(self) -> list[Path]:
        """Return immediate child Git worktrees.

        Returns:
            Sorted canonical worktree roots.
        """

        return sorted(
            (
                child.resolve()
                for child in self._workspace_root.iterdir()
                if child.is_dir() and ((child / ".git").is_dir() or (child / ".git").is_file())
            ),
            key=lambda path: path.name,
        )

    def _project_report_get(self, project_path: Path) -> ProjectReport:
        """Build exact mechanical metadata for one project.

        Args:
            project_path: Canonical project worktree root.

        Returns:
            Complete mechanical project report.
        """

        agents_path = project_path / "AGENTS.md"
        declared_project_standard_list = required_standard_name_list_get(agents_path)
        missing_project_standard_list = sorted(self._available_standard_set - set(declared_project_standard_list))
        missing_root_instruction_list = _missing_root_instruction_list_get(agents_path)
        task_root_issue_list = _task_root_issue_list_get(project_path)
        unavailable_project_standard_list = sorted(set(declared_project_standard_list) - self._available_standard_set)
        if (
            missing_project_standard_list
            or missing_root_instruction_list
            or task_root_issue_list
            or unavailable_project_standard_list
        ):
            mechanical_status = "finding"
        else:
            mechanical_status = "clean"
        return ProjectReport(
            declared_project_standard_list=declared_project_standard_list,
            git_common_dir=Path(
                _git_output_get(project_path, ["rev-parse", "--path-format=absolute", "--git-common-dir"])
            ).resolve(),
            mechanical_status=mechanical_status,
            missing_project_standard_list=missing_project_standard_list,
            missing_root_instruction_list=missing_root_instruction_list,
            path=project_path,
            task_root_issue_list=task_root_issue_list,
            unavailable_project_standard_list=unavailable_project_standard_list,
        )

    def report_print(self, workspace_report: WorkspaceReport) -> None:
        """Print deterministic JSON for one workspace report.

        Args:
            workspace_report: Complete mechanical workspace state.
        """

        print(
            json.dumps(
                {
                    "available_project_standard_list": sorted(self._available_standard_set),
                    "duplicate_git_common_dir_list": workspace_report["duplicate_git_common_dir_list"],
                    "mechanical_status": workspace_report["mechanical_status"],
                    "project_list": [
                        {
                            "declared_project_standard_list": project_report["declared_project_standard_list"],
                            "git_common_dir": str(project_report["git_common_dir"]),
                            "mechanical_status": project_report["mechanical_status"],
                            "missing_project_standard_list": project_report["missing_project_standard_list"],
                            "missing_root_instruction_list": project_report["missing_root_instruction_list"],
                            "path": str(project_report["path"]),
                            "semantic_audit_required": True,
                            "task_root_issue_list": project_report["task_root_issue_list"],
                            "unavailable_project_standard_list": project_report["unavailable_project_standard_list"],
                        }
                        for project_report in workspace_report["project_report_list"]
                    ],
                    "semantic_audit_required": True,
                    "workspace_root": str(self._workspace_root),
                },
                indent=2,
                sort_keys=True,
            )
        )

    def workspace_report_get(self) -> WorkspaceReport:
        """Build the complete workspace mechanical report.

        Returns:
            Project reports, duplicate worktrees, and aggregate status.
        """

        project_report_list = [self._project_report_get(project_path) for project_path in self._project_path_list_get()]
        common_dir_count_by_path_map: dict[Path, int] = {}
        for project_report in project_report_list:
            git_common_dir = project_report["git_common_dir"]
            common_dir_count_by_path_map[git_common_dir] = common_dir_count_by_path_map.get(git_common_dir, 0) + 1
        duplicate_git_common_dir_list = sorted(
            str(path) for path, count in common_dir_count_by_path_map.items() if count > 1
        )
        if any(project_report["mechanical_status"] != "clean" for project_report in project_report_list):
            mechanical_status = "finding"
        else:
            mechanical_status = "clean"
        return WorkspaceReport(
            duplicate_git_common_dir_list=duplicate_git_common_dir_list,
            mechanical_status=mechanical_status,
            project_report_list=project_report_list,
        )


class WorkspaceReport(TypedDict):
    """Store complete workspace mechanical inventory state."""

    duplicate_git_common_dir_list: list[str]
    mechanical_status: str
    project_report_list: list[ProjectReport]


if __name__ == "__main__":
    raise SystemExit(main())
