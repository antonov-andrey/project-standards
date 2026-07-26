"""Resolve repository-local Python modules, packages, and import dependencies."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from pathlib import Path


def absolute_import_module_name_get(
    current_package_part_list: Sequence[str],
    import_node: ast.ImportFrom,
) -> str | None:
    """Return one absolute module name for a from-import.

    Args:
        current_package_part_list: Current module package parts.
        import_node: Candidate from-import statement.

    Returns:
        Absolute target when relative traversal stays in the package tree.
    """

    if import_node.level == 0:
        return import_node.module
    if import_node.level - 1 > len(current_package_part_list):
        return None
    base_part_list = list(current_package_part_list[: len(current_package_part_list) - (import_node.level - 1)])
    if import_node.module:
        base_part_list.extend(import_node.module.split("."))
    return ".".join(base_part_list) if base_part_list else None


def longest_repository_module_name_get(
    module_name: str,
    relative_path_by_module_name_map: Mapping[str, str],
) -> str | None:
    """Return the longest repository-owned prefix of one dotted target.

    Args:
        module_name: Candidate dotted import target.
        relative_path_by_module_name_map: Repository paths keyed by module name.

    Returns:
        Longest known module prefix.
    """

    module_part_list = module_name.split(".")
    for index in range(len(module_part_list), 0, -1):
        candidate_module_name = ".".join(module_part_list[:index])
        if candidate_module_name in relative_path_by_module_name_map:
            return candidate_module_name
    return None


def module_name_get(relative_path: str) -> str:
    """Return an importable module name from one Python path.

    Args:
        relative_path: Repository-relative Python path.

    Returns:
        Dotted module name with an `__init__` suffix removed.
    """

    module_part_list = list(Path(relative_path).with_suffix("").parts)
    if module_part_list and module_part_list[-1] == "__init__":
        module_part_list = module_part_list[:-1]
    return ".".join(module_part_list)


def package_part_list_get(relative_path: str) -> list[str]:
    """Return package parts that own one Python module.

    Args:
        relative_path: Repository-relative Python path.

    Returns:
        Package components excluding the module filename.
    """

    part_list = list(Path(relative_path).with_suffix("").parts)
    return part_list[:-1]


def relative_path_by_module_name_map_get(relative_path_list: Sequence[str]) -> dict[str, str]:
    """Return repository Python paths keyed by importable module name.

    Args:
        relative_path_list: Repository-relative Python paths.

    Returns:
        Canonical module map including supported owner-local tool aliases.
    """

    relative_path_set = set(relative_path_list)
    source_root_index_set_by_path_map: dict[str, set[int]] = {}
    for relative_path in relative_path_list:
        part_list = list(Path(relative_path).parts)
        source_root_index_set: set[int] = set()
        for index, part in enumerate(part_list[:-2]):
            if part not in {"lib", "src"}:
                continue
            package_init_path = Path(*part_list[: index + 2], "__init__.py").as_posix()
            if package_init_path in relative_path_set and (index > 0 or part == "src"):
                source_root_index_set.add(index)
        source_root_index_set_by_path_map[relative_path] = source_root_index_set
    relative_path_by_module_name_map: dict[str, str] = {}
    for relative_path in relative_path_list:
        module_name = module_name_get(relative_path)
        if module_name:
            relative_path_by_module_name_map[module_name] = relative_path
        part_list = list(Path(relative_path).parts)
        for source_root_index in source_root_index_set_by_path_map[relative_path]:
            alias_part_list = list(Path(*part_list[source_root_index + 1 :]).with_suffix("").parts)
            if alias_part_list and alias_part_list[-1] == "__init__":
                alias_part_list = alias_part_list[:-1]
            if alias_part_list:
                relative_path_by_module_name_map[".".join(alias_part_list)] = relative_path
        if len(part_list) >= 6 and part_list[:2] == [".codex", "agents"] and part_list[3:5] == ["tool", "lib"]:
            alias_part_list = list(Path(*part_list[5:]).with_suffix("").parts)
            if alias_part_list and alias_part_list[-1] == "__init__":
                alias_part_list = alias_part_list[:-1]
            if alias_part_list:
                relative_path_by_module_name_map[".".join(alias_part_list)] = relative_path
    return relative_path_by_module_name_map


def repository_dependency_name_set_get(
    current_relative_path: str,
    module_node: ast.Module,
    relative_path_by_module_name_map: Mapping[str, str],
) -> set[str]:
    """Return repository-local imported module names for one parsed module.

    Args:
        current_relative_path: Path of the importing module.
        module_node: Parsed module.
        relative_path_by_module_name_map: Repository paths keyed by module name.

    Returns:
        Canonical direct dependency module names.
    """

    dependency_name_set: set[str] = set()
    package_part_list = package_part_list_get(current_relative_path)
    for node in ast.walk(module_node):
        if isinstance(node, ast.Import):
            for alias_node in node.names:
                imported_module_name = repository_module_name_get(
                    current_relative_path,
                    alias_node.name,
                    relative_path_by_module_name_map,
                )
                if imported_module_name is not None:
                    dependency_name_set.add(imported_module_name)
        elif isinstance(node, ast.ImportFrom):
            base_module_name = absolute_import_module_name_get(package_part_list, node)
            if base_module_name is None:
                continue
            imported_base_module_name = repository_module_name_get(
                current_relative_path,
                base_module_name,
                relative_path_by_module_name_map,
            )
            if imported_base_module_name is not None:
                dependency_name_set.add(imported_base_module_name)
            for alias_node in node.names:
                if alias_node.name == "*":
                    continue
                imported_module_name = repository_module_name_get(
                    current_relative_path,
                    f"{base_module_name}.{alias_node.name}",
                    relative_path_by_module_name_map,
                )
                if imported_module_name is not None:
                    dependency_name_set.add(imported_module_name)
    dependency_name_set.discard(module_name_get(current_relative_path))
    return dependency_name_set


def repository_module_name_get(
    current_relative_path: str,
    import_module_name: str,
    relative_path_by_module_name_map: Mapping[str, str],
) -> str | None:
    """Resolve one imported target to its canonical repository module.

    Args:
        current_relative_path: Path of the importing module.
        import_module_name: Dotted import target as written or absolutized.
        relative_path_by_module_name_map: Repository paths keyed by module name.

    Returns:
        Canonical module name when the target is repository-local.
    """

    imported_module_name = longest_repository_module_name_get(
        import_module_name,
        relative_path_by_module_name_map,
    )
    if imported_module_name is not None:
        imported_relative_path = relative_path_by_module_name_map[imported_module_name]
        return module_name_get(imported_relative_path)
    current_part_list = list(Path(current_relative_path).parts[:-1])
    import_part_list = import_module_name.split(".")
    for owner_root_name in ("scripts", "test", "tool"):
        if owner_root_name not in current_part_list:
            continue
        owner_root_index = len(current_part_list) - 1 - current_part_list[::-1].index(owner_root_name)
        candidate_part_list = [*current_part_list[: owner_root_index + 1], *import_part_list]
        for candidate_relative_path in (
            Path(*candidate_part_list).with_suffix(".py").as_posix(),
            Path(*candidate_part_list, "__init__.py").as_posix(),
        ):
            if candidate_relative_path not in relative_path_by_module_name_map.values():
                continue
            return module_name_get(candidate_relative_path)
    return None
