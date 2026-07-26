"""Resolve exact all and changed Git path scopes without semantic classification."""

from __future__ import annotations

from pathlib import Path

from project_standards.git_repository import git_output_get, submodule_name_by_path_map_get


def _git_current_relpath_list_get(project_root: Path) -> list[str]:
    """Return every tracked or non-ignored untracked current Git path.

    Args:
        project_root: Exact Git worktree root.

    Returns:
        Current repository-relative paths.
    """

    return _null_output_item_list_get(
        git_output_get(project_root, ["ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    )


def _git_diff_relpath_list_get(project_root: Path, argument_list: list[str]) -> list[str]:
    """Return old and new paths from one NUL-delimited name-status diff.

    Args:
        project_root: Git repository root.
        argument_list: Complete Git arguments for one name-status diff.

    Returns:
        Changed paths including both sides of rename and copy entries.

    Raises:
        ValueError: Git emits malformed name-status output.
    """

    item_list = _null_output_item_list_get(git_output_get(project_root, argument_list))
    relpath_list: list[str] = []
    index = 0
    while index < len(item_list):
        status = item_list[index]
        index += 1
        if not status:
            raise ValueError("Git name-status output contains one empty status")
        path_count = 2 if status[0] in {"C", "R"} else 1
        if index + path_count > len(item_list):
            raise ValueError("Git name-status output ended before its declared paths")
        relpath_list.extend(item_list[index : index + path_count])
        index += path_count
    return relpath_list


def _null_output_item_list_get(output: str) -> list[str]:
    """Return non-empty items from one NUL-delimited Git output.

    Args:
        output: Raw Git standard output.

    Returns:
        Ordered non-empty items.
    """

    return [item for item in output.split("\0") if item]


def _submodule_gitlink_changed_relpath_list_get(
    project_root: Path,
    submodule_relative_path: str,
    submodule_root: Path,
) -> list[str]:
    """Return paths changed between committed and checked-out Gitlink revisions.

    Args:
        project_root: Consumer repository root.
        submodule_relative_path: Direct Submodule path in the consumer.
        submodule_root: Exact checked-out Submodule root.

    Returns:
        Submodule-relative changed paths, or all current paths when the base is unavailable.
    """

    try:
        base_revision = git_output_get(
            project_root,
            ["rev-parse", f"HEAD:{submodule_relative_path}"],
        ).strip()
        git_output_get(submodule_root, ["cat-file", "-e", f"{base_revision}^{{commit}}"])
    except ValueError:
        return _git_current_relpath_list_get(submodule_root)
    target_revision = git_output_get(submodule_root, ["rev-parse", "HEAD"]).strip()
    if base_revision == target_revision:
        return []
    return _git_diff_relpath_list_get(
        submodule_root,
        ["diff", "--find-renames", "--name-status", "-z", base_revision, target_revision],
    )


def project_relpath_list_get(project_root: Path, scope: str) -> list[str]:
    """Return canonical repository paths including direct-Submodule contents.

    Args:
        project_root: Exact repository root.
        scope: `all` or `changed` path scope.

    Returns:
        Sorted unique repository-relative paths. Changed scope includes deletions.

    Raises:
        ValueError: Scope is unsupported or Git output is malformed.
    """

    if scope not in {"all", "changed"}:
        raise ValueError("Project path scope must be all or changed")
    submodule_name_by_path_map = submodule_name_by_path_map_get(project_root)
    if scope == "all":
        relpath_set = set(_git_current_relpath_list_get(project_root))
    else:
        relpath_set = set(
            _git_diff_relpath_list_get(
                project_root,
                ["diff", "--cached", "--find-renames", "--ignore-submodules=none", "--name-status", "-z"],
            )
        )
        relpath_set.update(
            _git_diff_relpath_list_get(
                project_root,
                ["diff", "--find-renames", "--ignore-submodules=none", "--name-status", "-z"],
            )
        )
        relpath_set.update(
            _null_output_item_list_get(
                git_output_get(project_root, ["ls-files", "--others", "--exclude-standard", "-z"])
            )
        )
    for submodule_relative_path in submodule_name_by_path_map:
        submodule_root = project_root / submodule_relative_path
        if not submodule_root.is_dir():
            continue
        if scope == "all":
            submodule_relpath_set = set(_git_current_relpath_list_get(submodule_root))
        else:
            submodule_relpath_set = set(
                _git_diff_relpath_list_get(
                    submodule_root,
                    ["diff", "--cached", "--find-renames", "--name-status", "-z"],
                )
            )
            submodule_relpath_set.update(
                _git_diff_relpath_list_get(
                    submodule_root,
                    ["diff", "--find-renames", "--name-status", "-z"],
                )
            )
            submodule_relpath_set.update(
                _null_output_item_list_get(
                    git_output_get(
                        submodule_root,
                        ["ls-files", "--others", "--exclude-standard", "-z"],
                    )
                )
            )
            if submodule_relative_path in relpath_set:
                submodule_relpath_set.update(
                    _submodule_gitlink_changed_relpath_list_get(
                        project_root=project_root,
                        submodule_relative_path=submodule_relative_path,
                        submodule_root=submodule_root,
                    )
                )
        relpath_set.update(
            f"{submodule_relative_path}/{relative_path}" for relative_path in submodule_relpath_set if relative_path
        )
    if scope == "changed":
        return sorted(relative_path for relative_path in relpath_set if relative_path)
    return sorted(
        relative_path
        for relative_path in relpath_set
        if relative_path and ((project_root / relative_path).exists() or (project_root / relative_path).is_symlink())
    )
