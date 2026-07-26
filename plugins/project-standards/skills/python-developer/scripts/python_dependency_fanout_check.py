#!/usr/bin/env python3

"""Detect oversized dependency fan-out in `Main project code` Python modules and classes."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys
from typing import TypedDict

from lib.checker_runtime import (
    function_arg_list_collect,
    import_root_set,
    main_project_scope_path_list_resolve,
    python_module_parse,
    scope_args_add,
)

DEPENDENCY_TOKEN_EXACT = {
    "session",
    "engine",
    "repo",
    "repository",
    "client",
    "logger",
    "config",
    "cache",
    "metrics",
    "service",
    "clock",
    "flags",
}
DEPENDENCY_TOKEN_PARTIAL = ("session", "repo", "client", "config", "logger", "cache", "metric", "service", "flag")


def args_parse() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed argument namespace.
    """

    parser = argparse.ArgumentParser(description="Detect oversized dependency fan-out in Main project Python code.")
    scope_args_add(
        parser,
        scope_help="Optional explicit Main project Python files/directories. When provided, --scope is ignored.",
    )
    parser.add_argument(
        "--max-import-roots",
        type=int,
        default=5,
        help="Maximum allowed imported root count before failure (default: 5).",
    )
    parser.add_argument(
        "--max-dependencies",
        type=int,
        default=5,
        help="Maximum allowed dependency-like constructor dependencies before failure (default: 5).",
    )
    return parser.parse_args()


def _is_dependency_like(name: str) -> bool:
    """Return whether one identifier looks dependency-like.

    Args:
        name: Identifier to classify.

    Returns:
        True when the identifier looks dependency-like.
    """

    lowered = name.lower()
    if lowered in DEPENDENCY_TOKEN_EXACT:
        return True
    return any(token in lowered for token in DEPENDENCY_TOKEN_PARTIAL)


def _module_finding_list_build(path: Path, *, max_import_roots: int, max_dependencies: int) -> list[Finding]:
    """Collect dependency fan-out findings for one module.

    Args:
        path: Repository-relative Python file path.
        max_import_roots: Maximum allowed imported root count.
        max_dependencies: Maximum allowed dependency-like collaborator count.

    Returns:
        Collected findings for the module.
    """

    finding_list: list[Finding] = []
    tree = python_module_parse(path)
    imported_root_set = import_root_set(tree)
    if len(imported_root_set) > max_import_roots:
        finding_list.append(
            Finding(
                path=path,
                lineno=1,
                owner=path.as_posix(),
                reason=(
                    "module dependency fan-out exceeds limit "
                    f"({len(imported_root_set)} imported roots > {max_import_roots})"
                ),
            )
        )

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        init_node = next(
            (
                child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == "__init__"
            ),
            None,
        )
        if init_node is None:
            continue
        dependency_argument_name_list = [
            name for name in function_arg_list_collect(init_node) if _is_dependency_like(name)
        ]
        stored_dependency_field_set = _stored_dependency_field_set(init_node)
        dependency_count = max(len(dependency_argument_name_list), len(stored_dependency_field_set))
        if dependency_count > max_dependencies:
            finding_list.append(
                Finding(
                    path=path,
                    lineno=init_node.lineno,
                    owner=node.name,
                    reason=(
                        "class dependency fan-out exceeds limit "
                        f"({dependency_count} dependency-like collaborators > {max_dependencies})"
                    ),
                )
            )
    return finding_list


def _stored_dependency_field_set(init_node: ast.AST) -> set[str]:
    """Collect stored dependency-like fields inside one constructor.

    Args:
        init_node: Constructor AST node.

    Returns:
        Stored dependency-like field names.
    """

    parameter_name_set = set(function_arg_list_collect(init_node))
    stored_dependency_field_set: set[str] = set()
    for statement in init_node.body:
        if not isinstance(statement, ast.Assign):
            continue
        if len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        value = statement.value
        if not isinstance(target, ast.Attribute) or not isinstance(target.value, ast.Name) or target.value.id != "self":
            continue
        if not isinstance(value, ast.Name) or value.id not in parameter_name_set:
            continue
        if _is_dependency_like(value.id):
            stored_dependency_field_set.add(target.attr)
    return stored_dependency_field_set


def main() -> int:
    """Run the checker CLI.

    Returns:
        Process exit code.
    """

    args = args_parse()
    scope = main_project_scope_path_list_resolve(args.paths, args.scope)
    finding_list: list[Finding] = []
    for path in scope:
        finding_list.extend(
            _module_finding_list_build(
                path, max_import_roots=args.max_import_roots, max_dependencies=args.max_dependencies
            )
        )

    if not finding_list:
        print("Python dependency fan-out check passed.")
        return 0

    for finding in finding_list:
        print(f"{finding['path']}:{finding['lineno']}: {finding['owner']}: {finding['reason']}.")
    print("FAIL: Python dependency fan-out check failed.")
    return 1


class Finding(TypedDict):
    """Represent one dependency fan-out finding."""

    lineno: int
    owner: str
    path: Path
    reason: str


if __name__ == "__main__":
    raise SystemExit(main())
