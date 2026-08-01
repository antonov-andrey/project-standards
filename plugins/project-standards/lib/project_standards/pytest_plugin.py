"""Explicit pytest discovery for repository and owner-local test roots."""

from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest

from project_standards.git_repository import git_output_get, submodule_name_by_path_map_get

IGNORED_PATH_PART_SET = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".worktree",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "tmp",
}
SUITE_ANCESTOR_PATH_SET_STASH_KEY = pytest.StashKey[set[Path]]()
SUITE_PATH_LIST_STASH_KEY = pytest.StashKey[list[Path]]()


def _is_ignored_path(path: Path, project_root: Path) -> bool:
    """Return whether one resolved path is outside owner-local discovery.

    Args:
        path: Candidate filesystem path.
        project_root: Exact pytest project root.

    Returns:
        Whether the path is outside the project or one ignored area.
    """

    try:
        relative_path = path.resolve().relative_to(project_root)
    except ValueError:
        return True
    return bool(set(relative_path.parts) & IGNORED_PATH_PART_SET)


def _skill_test_path_list_get(owner_root: Path) -> list[Path]:
    """Return tracked Skill-local test roots inside one Git owner.

    Args:
        owner_root: Root repository or direct submodule worktree.

    Returns:
        Sorted current Skill-local test roots.
    """

    skill_path_list = [
        owner_root / relative_path
        for relative_path in git_output_get(owner_root, ["ls-files", "-z"]).split("\0")
        if relative_path and Path(relative_path).name == "SKILL.md"
    ]
    return sorted(
        {test_path.resolve() for skill_path in skill_path_list if (test_path := skill_path.parent / "test").is_dir()},
        key=lambda path: path.as_posix(),
    )


def _suite_ancestor_path_set_get(project_root: Path, suite_path_list: list[Path]) -> set[Path]:
    """Return suite roots and ancestors needed for pytest traversal.

    Args:
        project_root: Exact pytest project root.
        suite_path_list: Discovered owner-local suite roots.

    Returns:
        Paths that pytest must traverse to reach every suite.
    """

    ancestor_path_set = {project_root}
    for suite_path in suite_path_list:
        current_path = suite_path
        while True:
            ancestor_path_set.add(current_path)
            if current_path == project_root:
                break
            current_path = current_path.parent
    return ancestor_path_set


def _suite_path_list_get(project_root: Path) -> list[Path]:
    """Return deterministic root, Skill, and direct-submodule test roots.

    Args:
        project_root: Exact pytest project root.

    Returns:
        Owner-local suite roots containing current pytest modules.
    """

    candidate_path_set: set[Path] = set()
    root_test_path = project_root / "test"
    if root_test_path.is_dir():
        candidate_path_set.add(root_test_path.resolve())
    candidate_path_set.update(_skill_test_path_list_get(project_root))
    for submodule_relative_path in submodule_name_by_path_map_get(project_root):
        submodule_root = (project_root / submodule_relative_path).resolve()
        if not submodule_root.is_dir():
            continue
        submodule_test_path = submodule_root / "test"
        if submodule_test_path.is_dir():
            candidate_path_set.add(submodule_test_path.resolve())
        candidate_path_set.update(_skill_test_path_list_get(submodule_root))
    return sorted(
        (
            suite_path
            for suite_path in candidate_path_set
            if not _is_ignored_path(suite_path, project_root)
            and any(
                path.is_file() and path.name.startswith("test_") and path.suffix == ".py"
                for path in suite_path.rglob("test_*.py")
            )
        ),
        key=lambda path: path.as_posix(),
    )


def pytest_configure(config: pytest.Config) -> None:
    """Discover and attach owner-local suite roots to pytest.

    Args:
        config: Active pytest configuration.
    """

    project_root = config.rootpath.resolve()
    try:
        git_root = Path(git_output_get(project_root, ["rev-parse", "--show-toplevel"]).strip()).resolve()
    except ValueError as error:
        raise pytest.UsageError(f"project_standards.pytest_plugin requires one Git worktree: {error}") from error
    if git_root != project_root:
        raise pytest.UsageError(
            f"project_standards.pytest_plugin root {project_root} is not the exact Git worktree root {git_root}"
        )
    suite_path_list = _suite_path_list_get(project_root)
    config.stash[SUITE_PATH_LIST_STASH_KEY] = suite_path_list
    config.stash[SUITE_ANCESTOR_PATH_SET_STASH_KEY] = _suite_ancestor_path_set_get(
        project_root,
        suite_path_list,
    )


def _match_pytest_option_ignored_path(path: Path, config: pytest.Config, project_root: Path) -> bool:
    """Return whether active pytest ignore options exclude one path.

    Args:
        path: Resolved candidate collection path.
        config: Active pytest configuration.
        project_root: Exact pytest project root.

    Returns:
        Whether `--ignore` or `--ignore-glob` excludes the path.
    """

    ignore_path_list = config.getoption("ignore") or []
    for ignore_path_text in ignore_path_list:
        ignore_path = Path(ignore_path_text)
        if not ignore_path.is_absolute():
            ignore_path = project_root / ignore_path
        ignore_path = ignore_path.resolve()
        if path == ignore_path or path.is_relative_to(ignore_path):
            return True
    if not path.is_relative_to(project_root):
        return False
    relative_path = path.relative_to(project_root).as_posix()
    return any(fnmatch.fnmatch(relative_path, pattern) for pattern in (config.getoption("ignore_glob") or []))


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Restrict collection to discovered owner-local suites.

    Args:
        collection_path: Candidate path considered by pytest.
        config: Active pytest configuration.

    Returns:
        True when ignored, otherwise None to preserve ordinary pytest selection.
    """

    project_root = config.rootpath.resolve()
    path = Path(str(collection_path)).resolve()
    if _match_pytest_option_ignored_path(path, config, project_root):
        return True
    if _is_ignored_path(path, project_root):
        return True
    suite_path_list = config.stash.get(SUITE_PATH_LIST_STASH_KEY, [])
    ancestor_path_set = config.stash.get(SUITE_ANCESTOR_PATH_SET_STASH_KEY, {project_root})
    if path == project_root or path in ancestor_path_set:
        return None
    if any(path == suite_path or path.is_relative_to(suite_path) for suite_path in suite_path_list):
        return None
    return True


def pytest_report_header(config: pytest.Config) -> str:
    """Return one deterministic owner-local discovery summary.

    Args:
        config: Active pytest configuration.

    Returns:
        Repository-relative suite list for the pytest header.
    """

    project_root = config.rootpath.resolve()
    suite_path_list = config.stash.get(SUITE_PATH_LIST_STASH_KEY, [])
    relative_path_list = [path.relative_to(project_root).as_posix() for path in suite_path_list]
    return "project-standard pytest suites: " + ", ".join(relative_path_list)
