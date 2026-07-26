"""Resolve repository-local Python classes and inheritance relationships."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from pathlib import Path

from project_standards.python_import import (
    absolute_import_module_name_get,
    module_name_get,
    package_part_list_get,
)


def python_class_base_fqn_set_by_fqn_map_get(
    class_node_by_fqn_map: Mapping[str, ast.ClassDef],
    project_root: Path,
    relative_path_list: Sequence[str],
) -> dict[str, set[str]]:
    """Return repository-local direct base-class FQNs keyed by class FQN.

    Args:
        class_node_by_fqn_map: Repository class nodes keyed by FQN.
        project_root: Exact repository root.
        relative_path_list: Python paths that own the class scope.

    Returns:
        Direct repository-local inheritance edges.
    """

    class_fqn_set = set(class_node_by_fqn_map)
    target_fqn_by_import_fqn_map = python_class_target_fqn_by_import_fqn_map_get(
        class_node_by_fqn_map,
        project_root,
        relative_path_list,
    )
    base_fqn_set_by_fqn_map: dict[str, set[str]] = {class_fqn: set() for class_fqn in class_fqn_set}
    for relative_path in relative_path_list:
        try:
            module_node = ast.parse(
                (project_root / relative_path).read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except OSError, SyntaxError:
            continue
        module_name = module_name_get(relative_path)
        class_fqn_by_local_name_map = {
            child_node.name: f"{module_name}.{child_node.name}"
            for child_node in module_node.body
            if isinstance(child_node, ast.ClassDef)
        }
        module_name_by_local_name_map: dict[str, str] = {}
        for child_node in module_node.body:
            if isinstance(child_node, ast.Import):
                for alias_node in child_node.names:
                    module_name_by_local_name_map[alias_node.asname or alias_node.name.split(".", maxsplit=1)[0]] = (
                        alias_node.name
                    )
            elif isinstance(child_node, ast.ImportFrom):
                imported_module_name = absolute_import_module_name_get(
                    package_part_list_get(relative_path),
                    child_node,
                )
                if imported_module_name is None:
                    continue
                for alias_node in child_node.names:
                    candidate_fqn = f"{imported_module_name}.{alias_node.name}"
                    target_fqn = target_fqn_by_import_fqn_map.get(candidate_fqn)
                    if target_fqn is not None:
                        class_fqn_by_local_name_map[alias_node.asname or alias_node.name] = target_fqn
        for child_node in module_node.body:
            if not isinstance(child_node, ast.ClassDef):
                continue
            class_fqn = f"{module_name}.{child_node.name}"
            for base_node in child_node.bases:
                base_fqn: str | None = None
                if isinstance(base_node, ast.Name):
                    base_fqn = class_fqn_by_local_name_map.get(base_node.id)
                elif isinstance(base_node, ast.Attribute) and isinstance(base_node.value, ast.Name):
                    imported_module_name = module_name_by_local_name_map.get(base_node.value.id)
                    candidate_fqn = f"{imported_module_name}.{base_node.attr}" if imported_module_name else ""
                    base_fqn = target_fqn_by_import_fqn_map.get(candidate_fqn)
                if base_fqn is not None:
                    base_fqn_set_by_fqn_map[class_fqn].add(base_fqn)
    return base_fqn_set_by_fqn_map


def python_class_base_name_set_by_fqn_map_get(
    class_node_by_fqn_map: Mapping[str, ast.ClassDef],
) -> dict[str, set[str]]:
    """Return visible direct base names keyed by class FQN.

    Args:
        class_node_by_fqn_map: Repository class nodes keyed by FQN.

    Returns:
        Direct base name tokens for each class.
    """

    return {
        class_fqn: {
            base_node.id if isinstance(base_node, ast.Name) else base_node.attr
            for base_node in class_node.bases
            if isinstance(base_node, (ast.Attribute, ast.Name))
        }
        for class_fqn, class_node in class_node_by_fqn_map.items()
    }


def python_class_descendant_fqn_set_get(
    base_fqn_set_by_fqn_map: Mapping[str, set[str]],
    seed_class_fqn_set: set[str],
) -> set[str]:
    """Return seeds and all repository-local transitive descendants.

    Args:
        base_fqn_set_by_fqn_map: Direct inheritance edges keyed by class.
        seed_class_fqn_set: Initial class FQNs.

    Returns:
        Transitive descendant closure including the seed classes.
    """

    descendant_class_fqn_set = set(seed_class_fqn_set)
    changed = True
    while changed:
        changed = False
        for class_fqn, base_fqn_set in base_fqn_set_by_fqn_map.items():
            if class_fqn in descendant_class_fqn_set or not base_fqn_set & descendant_class_fqn_set:
                continue
            descendant_class_fqn_set.add(class_fqn)
            changed = True
    return descendant_class_fqn_set


def python_class_node_by_fqn_map_get(
    project_root: Path,
    relative_path_list: Sequence[str],
) -> dict[str, ast.ClassDef]:
    """Return top-level repository class nodes keyed by FQN.

    Args:
        project_root: Exact repository root.
        relative_path_list: Python definition paths.

    Returns:
        Parsed top-level class nodes.
    """

    class_node_by_fqn_map: dict[str, ast.ClassDef] = {}
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
            if isinstance(child_node, ast.ClassDef):
                class_node_by_fqn_map[f"{module_name}.{child_node.name}"] = child_node
    return class_node_by_fqn_map


def python_class_target_fqn_by_import_fqn_map_get(
    class_node_by_fqn_map: Mapping[str, ast.ClassDef],
    project_root: Path,
    relative_path_list: Sequence[str],
) -> dict[str, str]:
    """Return import and re-export identities mapped to defining class FQNs.

    Args:
        class_node_by_fqn_map: Repository class nodes keyed by FQN.
        project_root: Exact repository root.
        relative_path_list: Python paths that own the class scope.

    Returns:
        Every resolvable repository import identity mapped to its defining class.
    """

    target_fqn_by_import_fqn_map = {class_fqn: class_fqn for class_fqn in class_node_by_fqn_map}
    changed = True
    while changed:
        changed = False
        for relative_path in relative_path_list:
            try:
                module_node = ast.parse(
                    (project_root / relative_path).read_text(encoding="utf-8"),
                    filename=relative_path,
                )
            except OSError, SyntaxError:
                continue
            current_module_name = module_name_get(relative_path)
            for child_node in module_node.body:
                if not isinstance(child_node, ast.ImportFrom):
                    continue
                imported_module_name = absolute_import_module_name_get(
                    package_part_list_get(relative_path),
                    child_node,
                )
                if imported_module_name is None:
                    continue
                for alias_node in child_node.names:
                    source_fqn = f"{imported_module_name}.{alias_node.name}"
                    target_fqn = target_fqn_by_import_fqn_map.get(source_fqn)
                    export_fqn = f"{current_module_name}.{alias_node.asname or alias_node.name}"
                    if target_fqn is None or target_fqn_by_import_fqn_map.get(export_fqn) == target_fqn:
                        continue
                    target_fqn_by_import_fqn_map[export_fqn] = target_fqn
                    changed = True
    return target_fqn_by_import_fqn_map
