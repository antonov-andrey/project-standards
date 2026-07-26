"""Resolve repository, Python, Legacy, and Main project path scopes."""

from __future__ import annotations

import ast
from pathlib import Path

from project_standards.git_repository import git_output_get, submodule_name_by_path_map_get

MODELED_MAIN_PROJECT_ROOT_SET = {
    "backend",
    "deploy",
    "lib",
    "model_sqlalchemy",
    "plugins",
    "script",
    "src",
    "ui",
}


def _entrypoint_run_target_get(source: str) -> str | None:
    """Return the canonical target of one thin root entrypoint.

    Args:
        source: Python source of one root entrypoint candidate.

    Returns:
        Imported `module:main` target when the source is one recognized wrapper.
    """

    try:
        module = ast.parse(source)
    except SyntaxError:
        return None
    entrypoint_run_name_set: set[str] = set()
    main_import_module_by_local_name_map: dict[str, str] = {}
    main_guard: ast.If | None = None
    for node in module.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if isinstance(node, ast.ImportFrom):
            if node.module == "lib.entrypoint":
                for alias in node.names:
                    if alias.name == "entrypoint_run":
                        entrypoint_run_name_set.add(alias.asname or alias.name)
                continue
            if node.module:
                for alias in node.names:
                    if alias.name == "main":
                        main_import_module_by_local_name_map[alias.asname or alias.name] = node.module
                continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if _is_main_guard_node_match(node):
            if main_guard is not None:
                return None
            main_guard = node
            continue
        return None
    if main_guard is None or len(main_guard.body) != 1 or main_guard.orelse or not entrypoint_run_name_set:
        return None
    statement = main_guard.body[0]
    if not isinstance(statement, ast.Raise):
        return None
    exception = statement.exc
    if not isinstance(exception, ast.Call):
        return None
    if not isinstance(exception.func, ast.Name) or exception.func.id != "SystemExit":
        return None
    if len(exception.args) != 1 or exception.keywords:
        return None
    call = exception.args[0]
    if not isinstance(call, ast.Call):
        return None
    if not isinstance(call.func, ast.Name) or call.func.id not in entrypoint_run_name_set:
        return None
    if len(call.args) != 1 or call.keywords or not isinstance(call.args[0], ast.Name):
        return None
    module_name = main_import_module_by_local_name_map.get(call.args[0].id)
    return f"{module_name}:main" if module_name is not None else None


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


def _is_main_guard_node_match(node: ast.stmt) -> bool:
    """Return whether one AST node is the canonical main guard.

    Args:
        node: Candidate AST statement.

    Returns:
        Whether the node is `if __name__ == "__main__":`.
    """

    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare):
        return False
    if len(test.ops) != 1 or len(test.comparators) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    return (
        isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def _legacy_root_name_get(
    project_root: Path,
    python_relpath_set: set[str],
    relative_path: str,
    submodule_root_set: set[str],
) -> str | None:
    """Return the Legacy owner root of one Python path.

    Args:
        project_root: Exact repository root.
        python_relpath_set: Complete current Python scope.
        relative_path: Candidate repository-relative Python path.
        submodule_root_set: Direct submodule root paths.

    Returns:
        Legacy root directory name when the path belongs to Legacy.
    """

    if "/" in relative_path:
        root_name = relative_path.split("/", maxsplit=1)[0]
        return (
            root_name
            if _match_legacy_root_name(
                python_relpath_set=python_relpath_set,
                root_name=root_name,
                submodule_root_set=submodule_root_set,
            )
            else None
        )
    try:
        source = (project_root / relative_path).read_text(encoding="utf-8")
    except OSError:
        return None
    target = _entrypoint_run_target_get(source)
    if target is None:
        return None
    root_name = target.split(":", maxsplit=1)[0].split(".", maxsplit=1)[0]
    return (
        root_name
        if _match_legacy_root_name(
            python_relpath_set=python_relpath_set,
            root_name=root_name,
            submodule_root_set=submodule_root_set,
        )
        else None
    )


def _match_legacy_root_name(
    python_relpath_set: set[str],
    root_name: str,
    submodule_root_set: set[str],
) -> bool:
    """Return whether one root directory is a Legacy owner.

    Args:
        python_relpath_set: Complete current Python scope.
        root_name: Candidate repository-root directory name.
        submodule_root_set: Direct submodule root paths.

    Returns:
        Whether the root is unmodeled Python outside tests, tools, and submodules.
    """

    if (
        not root_name
        or root_name.startswith(".")
        or root_name in MODELED_MAIN_PROJECT_ROOT_SET
        or root_name in {"test", "tool"}
        or root_name in submodule_root_set
    ):
        return False
    return any(relative_path.startswith(f"{root_name}/") for relative_path in python_relpath_set)


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
    """Return paths changed between committed and checked-out gitlink revisions.

    Args:
        project_root: Consumer repository root.
        submodule_relative_path: Direct submodule path in the consumer.
        submodule_root: Exact checked-out submodule root.

    Returns:
        Submodule-relative changed paths, or all current paths when the base is unavailable.
    """

    try:
        base_revision = git_output_get(
            project_root,
            ["rev-parse", f"HEAD:{submodule_relative_path}"],
        ).strip()
        target_revision = git_output_get(submodule_root, ["rev-parse", "HEAD"]).strip()
        if base_revision == target_revision:
            return []
        return _git_diff_relpath_list_get(
            submodule_root,
            ["diff", "--find-renames", "--name-status", "-z", base_revision, target_revision],
        )
    except ValueError:
        return _null_output_item_list_get(
            git_output_get(submodule_root, ["ls-files", "--cached", "--others", "--exclude-standard", "-z"])
        )


def legacy_python_relpath_list_get(project_root: Path, scope: str = "all") -> list[str]:
    """Return Python paths that belong to Legacy.

    Args:
        project_root: Exact repository root.
        scope: `all` or `changed` path scope.

    Returns:
        Sorted repository-relative Legacy Python paths.
    """

    all_python_relpath_list = python_relpath_list_get(project_root, scope="all")
    selected_python_relpath_set = set(python_relpath_list_get(project_root, scope=scope))
    python_relpath_set = set(all_python_relpath_list)
    submodule_root_set = set(submodule_name_by_path_map_get(project_root))
    return [
        relative_path
        for relative_path in all_python_relpath_list
        if relative_path in selected_python_relpath_set
        and _legacy_root_name_get(
            project_root=project_root,
            python_relpath_set=python_relpath_set,
            relative_path=relative_path,
            submodule_root_set=submodule_root_set,
        )
        is not None
    ]


def main_project_python_relpath_list_get(project_root: Path, scope: str = "all") -> list[str]:
    """Return the Python subset of Main project code.

    Args:
        project_root: Exact repository root.
        scope: `all` or `changed` path scope.

    Returns:
        Sorted repository-relative Main project Python paths.
    """

    all_python_relpath_list = python_relpath_list_get(project_root, scope="all")
    selected_python_relpath_set = set(python_relpath_list_get(project_root, scope=scope))
    python_relpath_set = set(all_python_relpath_list)
    submodule_root_set = set(submodule_name_by_path_map_get(project_root))
    legacy_python_relpath_set = set(legacy_python_relpath_list_get(project_root, scope="all"))
    return [
        relative_path
        for relative_path in all_python_relpath_list
        if relative_path in selected_python_relpath_set
        and relative_path != "conftest.py"
        and not relative_path.startswith((".codex/", "test/", "tool/"))
        and not any(
            relative_path == submodule_root or relative_path.startswith(f"{submodule_root}/")
            for submodule_root in submodule_root_set
        )
        and relative_path not in legacy_python_relpath_set
        and relative_path in python_relpath_set
    ]


def non_legacy_non_test_python_outside_submodule_relpath_list_get(
    project_root: Path,
    scope: str = "all",
) -> list[str]:
    """Return definition paths for root-repository Python contracts.

    Args:
        project_root: Exact repository root.
        scope: `all` or `changed` path scope.

    Returns:
        Sorted non-Legacy, non-test Python paths outside direct submodules.
    """

    selected_python_relpath_set = set(python_relpath_list_get(project_root, scope=scope))
    legacy_python_relpath_set = set(legacy_python_relpath_list_get(project_root, scope="all"))
    submodule_root_set = set(submodule_name_by_path_map_get(project_root))
    return [
        relative_path
        for relative_path in python_relpath_list_get(project_root, scope="all")
        if relative_path in selected_python_relpath_set
        and relative_path != "conftest.py"
        and relative_path not in legacy_python_relpath_set
        and "test" not in Path(relative_path).parts
        and not any(
            relative_path == submodule_root or relative_path.startswith(f"{submodule_root}/")
            for submodule_root in submodule_root_set
        )
    ]


def non_legacy_non_test_python_relpath_list_get(project_root: Path, scope: str = "all") -> list[str]:
    """Return non-Legacy Python paths outside owner-local test roots.

    Args:
        project_root: Exact repository root.
        scope: `all` or `changed` path scope.

    Returns:
        Sorted applicable root and direct-submodule Python paths.
    """

    selected_python_relpath_set = set(python_relpath_list_get(project_root, scope=scope))
    legacy_python_relpath_set = set(legacy_python_relpath_list_get(project_root, scope="all"))
    return [
        relative_path
        for relative_path in python_relpath_list_get(project_root, scope="all")
        if relative_path in selected_python_relpath_set
        and relative_path not in legacy_python_relpath_set
        and "test" not in Path(relative_path).parts
    ]


def project_relpath_list_get(project_root: Path, scope: str) -> list[str]:
    """Return canonical repository paths including direct-submodule contents.

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
        relpath_set = set(
            _null_output_item_list_get(
                git_output_get(project_root, ["ls-files", "--cached", "--others", "--exclude-standard", "-z"])
            )
        )
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
            submodule_relpath_set = set(
                _null_output_item_list_get(
                    git_output_get(
                        submodule_root,
                        ["ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                    )
                )
            )
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


def python_relpath_list_get(project_root: Path, scope: str = "all") -> list[str]:
    """Return current Python files from one repository scope.

    Args:
        project_root: Exact repository root.
        scope: `all` or `changed` path scope.

    Returns:
        Sorted current `.py` paths, including direct-submodule files.
    """

    return [
        relative_path
        for relative_path in project_relpath_list_get(project_root, scope)
        if relative_path.endswith(".py") and (project_root / relative_path).is_file()
    ]
