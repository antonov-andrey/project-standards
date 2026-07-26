#!/usr/bin/env python3

"""Detect generic bucket modules that accumulate heterogeneous content."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys
from typing import TypedDict

from lib.checker_runtime import (
    import_root_set,
    main_project_scope_path_list_resolve,
    python_module_parse,
    scope_args_add,
)

BUCKET_MODULE_NAMES = {"utils", "helpers", "services", "runtime", "common", "misc"}


def args_parse() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed argument namespace.
    """

    parser = argparse.ArgumentParser(description="Detect generic bucket modules in Main project Python code.")
    scope_args_add(
        parser,
        scope_help="Optional explicit Main project Python files/directories. When provided, --scope is ignored.",
    )
    parser.add_argument(
        "--min-import-roots",
        type=int,
        default=3,
        help="Minimum imported-root count for a bucket-module finding (default: 3).",
    )
    parser.add_argument(
        "--min-symbols",
        type=int,
        default=4,
        help="Minimum top-level symbol count for a bucket-module finding (default: 4).",
    )
    parser.add_argument(
        "--min-prefixes",
        type=int,
        default=3,
        help="Minimum distinct top-level symbol prefixes for a bucket-module finding (default: 3).",
    )
    return parser.parse_args()


def _category_count(tree: ast.Module) -> int:
    """Count top-level symbol categories present in one module.

    Args:
        tree: Parsed module AST.

    Returns:
        Count of present top-level symbol categories.
    """

    category_set: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            category_set.add("function")
            continue
        if isinstance(node, ast.ClassDef):
            category_set.add("class")
            continue
        if isinstance(node, ast.Assign):
            category_set.add("constant")
    return len(category_set)


def _module_analyze(
    path: Path,
    *,
    min_import_roots: int,
    min_symbols: int,
    min_prefixes: int,
) -> Finding | None:
    """Return one bucket-module finding when the module is heterogeneous enough.

    Args:
        path: Repository-relative Python file path.
        min_import_roots: Minimum imported-root count.
        min_symbols: Minimum top-level symbol count.
        min_prefixes: Minimum distinct top-level symbol-prefix count.

    Returns:
        One finding for a heterogeneous bucket module, else `None`.
    """

    if path.stem not in BUCKET_MODULE_NAMES:
        return None

    tree = python_module_parse(path)
    imported_root_set = import_root_set(tree)
    symbol_name_list = _top_level_symbol_name_list_build(tree)
    symbol_prefix_set = _symbol_prefix_set(symbol_name_list)
    category_count = _category_count(tree)
    if len(imported_root_set) < min_import_roots:
        return None
    if len(symbol_name_list) < min_symbols:
        return None
    if len(symbol_prefix_set) < min_prefixes:
        return None
    if category_count < 2:
        return None
    return Finding(
        path=path,
        import_root_count=len(imported_root_set),
        symbol_count=len(symbol_name_list),
        category_count=category_count,
        prefix_count=len(symbol_prefix_set),
    )


def _symbol_prefix_set(name_list: list[str]) -> set[str]:
    """Normalize top-level symbols into coarse prefixes.

    Args:
        name_list: Top-level symbol names.

    Returns:
        Distinct coarse symbol prefixes.
    """

    prefix_set: set[str] = set()
    for name in name_list:
        normalized = name.lstrip("_")
        if not normalized:
            continue
        prefix_set.add(normalized.split("_", 1)[0].lower())
    return prefix_set


def _top_level_symbol_name_list_build(tree: ast.Module) -> list[str]:
    """Collect top-level symbol names that contribute to module heterogeneity.

    Args:
        tree: Parsed module AST.

    Returns:
        Top-level symbol names.
    """

    name_list: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name_list.append(node.name)
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name_list.append(target.id)
    return name_list


def main() -> int:
    """Run the checker CLI.

    Returns:
        Process exit code.
    """

    args = args_parse()
    scope = main_project_scope_path_list_resolve(args.paths, args.scope)
    finding_list = [
        finding
        for path in scope
        if (
            finding := _module_analyze(
                path,
                min_import_roots=args.min_import_roots,
                min_symbols=args.min_symbols,
                min_prefixes=args.min_prefixes,
            )
        )
        is not None
    ]

    if not finding_list:
        print("Python generic bucket-module check passed.")
        return 0

    for finding in finding_list:
        print(
            f"{finding['path']}: generic bucket module is heterogeneous enough to fail "
            f"(imports={finding['import_root_count']}, symbols={finding['symbol_count']}, "
            f"categories={finding['category_count']}, prefixes={finding['prefix_count']})."
        )
    print("FAIL: Python generic bucket-module check failed.")
    return 1


class Finding(TypedDict):
    """Represent one generic-bucket finding."""

    category_count: int
    import_root_count: int
    path: Path
    prefix_count: int
    symbol_count: int


if __name__ == "__main__":
    raise SystemExit(main())
