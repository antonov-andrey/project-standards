"""Reusable static Python syntax queries for capability checkers."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

from project_standards.project_scope import python_relpath_list_get
from project_standards.python_import import relative_path_by_module_name_map_get


def call_name_get(node: ast.AST) -> str | None:
    """Return one direct or attribute call-target name.

    Args:
        node: Candidate call or callable expression.

    Returns:
        Visible name, otherwise `None`.
    """

    callable_node = node.func if isinstance(node, ast.Call) else node
    if isinstance(callable_node, ast.Name):
        return callable_node.id
    if isinstance(callable_node, ast.Attribute):
        return callable_node.attr
    return None


def class_base_name_set_get(class_node: ast.ClassDef) -> set[str]:
    """Return direct visible base names for one class.

    Args:
        class_node: Candidate class definition.

    Returns:
        Direct name and attribute base names.
    """

    return {base_name for base_node in class_node.bases if (base_name := call_name_get(base_node)) is not None}


def import_group_name_get(
    import_node: ast.stmt,
    repository_module_root_name_set: set[str],
) -> str:
    """Return one import statement's canonical group.

    Args:
        import_node: Candidate import statement.
        repository_module_root_name_set: Root module names owned by the repository.

    Returns:
        `stdlib`, `third_party`, or `repository_local`.
    """

    if isinstance(import_node, ast.Import):
        module_name = import_node.names[0].name
    else:
        if import_node.level > 0:
            return "repository_local"
        module_name = import_node.module or ""
    root_name = module_name.split(".", maxsplit=1)[0]
    if root_name == "__future__" or root_name in sys.stdlib_module_names:
        return "stdlib"
    if root_name == "lib" or root_name in repository_module_root_name_set:
        return "repository_local"
    return "third_party"


def repository_module_root_name_set_get(project_root: Path) -> set[str]:
    """Return import-root names owned by one repository and its submodules.

    Args:
        project_root: Exact repository root.

    Returns:
        Root module names, including direct owner-local tool aliases.
    """

    relative_path_list = python_relpath_list_get(project_root, scope="all")
    root_name_set = {
        module_name.split(".", maxsplit=1)[0]
        for module_name in relative_path_by_module_name_map_get(relative_path_list)
    }
    for relative_path in relative_path_list:
        path = Path(relative_path)
        root_name_set.add(path.parts[0] if len(path.parts) > 1 else path.stem)
        part_list = list(path.parts)
        if len(part_list) >= 6 and part_list[:2] == [".codex", "agents"] and part_list[3:5] == ["tool", "lib"]:
            module_part_list = list(Path(*part_list[5:]).with_suffix("").parts)
            if module_part_list and module_part_list[-1] == "__init__":
                module_part_list = module_part_list[:-1]
            if module_part_list:
                root_name_set.add(module_part_list[0])
    return root_name_set
