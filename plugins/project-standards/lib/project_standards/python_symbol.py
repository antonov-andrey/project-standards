"""Resolve repository-local top-level Python symbol definitions and uses."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path

from project_standards.project_standard_model import ProjectStandardPythonSymbolDefinition
from project_standards.python_import import (
    absolute_import_module_name_get,
    module_name_get,
    package_part_list_get,
    relative_path_by_module_name_map_get,
    repository_module_name_get,
)


def local_load_line_set_by_name_map_get(module_node: ast.Module) -> dict[str, set[int]]:
    """Return same-module load lines keyed by simple symbol name.

    Args:
        module_node: Parsed module.

    Returns:
        Load-site line numbers grouped by name.
    """

    line_set_by_name_map: dict[str, set[int]] = {}
    for node in ast.walk(module_node):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            line_set_by_name_map.setdefault(node.id, set()).add(node.lineno)
    return line_set_by_name_map


def python_symbol_definition_by_fqn_map_get(
    project_root: Path,
    relative_path_list: Sequence[str],
) -> dict[str, ProjectStandardPythonSymbolDefinition]:
    """Return top-level class and function definitions keyed by FQN.

    Args:
        project_root: Exact repository root.
        relative_path_list: Definition-scope Python paths.

    Returns:
        Definition records keyed by fully qualified symbol name.
    """

    definition_by_fqn_map: dict[str, ProjectStandardPythonSymbolDefinition] = {}
    for relative_path in relative_path_list:
        try:
            module_node = ast.parse(
                (project_root / relative_path).read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except OSError, SyntaxError:
            continue
        module_name = module_name_get(relative_path)
        for child_node in module_node.body:
            if isinstance(child_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                kind = "function"
            elif isinstance(child_node, ast.ClassDef):
                kind = "class"
            else:
                continue
            symbol_fqn = f"{module_name}.{child_node.name}"
            definition_by_fqn_map[symbol_fqn] = ProjectStandardPythonSymbolDefinition(
                kind=kind,
                line=child_node.lineno,
                module_name=module_name,
                name=child_node.name,
                path=relative_path,
            )
    return definition_by_fqn_map


def python_symbol_use_path_set_by_fqn_map_get(
    project_root: Path,
    relative_path_list: Sequence[str],
) -> dict[str, set[str]]:
    """Return repository-local symbol use paths keyed by FQN.

    Args:
        project_root: Exact repository root.
        relative_path_list: Complete Python use-scan paths.

    Returns:
        Repository paths grouped by referenced symbol FQN.
    """

    relative_path_by_module_name_map = relative_path_by_module_name_map_get(relative_path_list)
    use_path_set_by_fqn_map: dict[str, set[str]] = {}
    for relative_path in relative_path_list:
        try:
            module_node = ast.parse(
                (project_root / relative_path).read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except OSError, SyntaxError:
            continue
        module_name_by_local_name_map: dict[str, str] = {}
        symbol_fqn_by_local_name_map: dict[str, str] = {}
        package_part_list = package_part_list_get(relative_path)
        for node in ast.walk(module_node):
            if isinstance(node, ast.Import):
                for alias_node in node.names:
                    imported_module_name = repository_module_name_get(
                        relative_path,
                        alias_node.name,
                        relative_path_by_module_name_map,
                    )
                    if imported_module_name is None:
                        continue
                    local_name = alias_node.asname or alias_node.name.split(".", maxsplit=1)[0]
                    module_name_by_local_name_map[local_name] = imported_module_name
            elif isinstance(node, ast.ImportFrom):
                base_module_name = absolute_import_module_name_get(package_part_list, node)
                if base_module_name is None:
                    continue
                canonical_base_module_name = repository_module_name_get(
                    relative_path,
                    base_module_name,
                    relative_path_by_module_name_map,
                )
                for alias_node in node.names:
                    if alias_node.name == "*":
                        continue
                    local_name = alias_node.asname or alias_node.name
                    candidate_module_name = f"{base_module_name}.{alias_node.name}"
                    imported_module_name = repository_module_name_get(
                        relative_path,
                        candidate_module_name,
                        relative_path_by_module_name_map,
                    )
                    if imported_module_name == candidate_module_name:
                        module_name_by_local_name_map[local_name] = imported_module_name
                    if canonical_base_module_name is not None:
                        symbol_fqn = f"{canonical_base_module_name}.{alias_node.name}"
                        symbol_fqn_by_local_name_map[local_name] = symbol_fqn
                        use_path_set_by_fqn_map.setdefault(symbol_fqn, set()).add(relative_path)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                if isinstance(node.value, ast.Name):
                    imported_module_name = module_name_by_local_name_map.get(node.value.id)
                    if imported_module_name is not None:
                        use_path_set_by_fqn_map.setdefault(f"{imported_module_name}.{node.attr}", set()).add(
                            relative_path
                        )
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                symbol_fqn = symbol_fqn_by_local_name_map.get(node.id)
                if symbol_fqn is not None:
                    use_path_set_by_fqn_map.setdefault(symbol_fqn, set()).add(relative_path)
    return use_path_set_by_fqn_map
