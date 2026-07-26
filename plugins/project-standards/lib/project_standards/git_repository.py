"""Read-only Git repository queries shared by project-standard tooling."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import subprocess


def git_output_get(project_root: Path, argument_sequence: Sequence[str]) -> str:
    """Return one successful Git command's standard output.

    Args:
        project_root: Repository root or path inside the target worktree.
        argument_sequence: Arguments passed after the Git executable.

    Returns:
        Unmodified standard output text.

    Raises:
        ValueError: Git rejects the command.
    """

    result = subprocess.run(
        ["git", "-C", str(project_root), *argument_sequence],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Git command failed"
        raise ValueError(message)
    return result.stdout


def submodule_name_by_path_map_get(project_root: Path) -> dict[str, str]:
    """Return direct Git submodule names keyed by repository-relative path.

    Args:
        project_root: Exact root of the consumer Git worktree.

    Returns:
        Deterministically ordered direct submodule name map.
    """

    gitmodules_path = project_root / ".gitmodules"
    if not gitmodules_path.is_file():
        return {}
    output = git_output_get(
        project_root,
        ["config", "--file", str(gitmodules_path), "--get-regexp", r"^submodule\..*\.path$"],
    )
    submodule_name_by_path_map: dict[str, str] = {}
    for line in output.splitlines():
        key, relative_path = line.split(maxsplit=1)
        submodule_name = key.removeprefix("submodule.").removesuffix(".path")
        submodule_name_by_path_map[Path(relative_path).as_posix()] = submodule_name
    return dict(sorted(submodule_name_by_path_map.items()))
