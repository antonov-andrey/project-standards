#!/usr/bin/env python3
"""Check that static multiline strings have one module-level owner."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import legacy_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest


def _docstring_value_identity_set_get(module_node: ast.Module) -> set[int]:
    """Return syntax identities for every real docstring value.

    Args:
        module_node: Parsed module.

    Returns:
        Identity set of module, class, and callable docstring constants.
    """

    identity_set: set[int] = set()
    for owner_node in [module_node, *ast.walk(module_node)]:
        if not isinstance(owner_node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Module)):
            continue
        body_node_list = owner_node.body
        if not body_node_list or not isinstance(body_node_list[0], ast.Expr):
            continue
        value_node = body_node_list[0].value
        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            identity_set.add(id(value_node))
    return identity_set


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return misplaced static multiline-string findings.

    Args:
        request: Validated checker request.

    Returns:
        File and line findings for non-test non-Legacy Python.
    """

    project_root = Path(request["project_root"])
    legacy_relative_path_set = set(legacy_python_relpath_list_get(project_root))
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        path_part_set = set(Path(relative_path).parts)
        if (
            not relative_path.endswith(".py")
            or relative_path in legacy_relative_path_set
            or "test" in path_part_set
            or not path.is_file()
        ):
            continue
        source = path.read_text(encoding="utf-8")
        try:
            module_node = ast.parse(source, filename=relative_path)
        except SyntaxError:
            continue
        parent_by_identity_map = {
            id(child_node): parent_node
            for parent_node in ast.walk(module_node)
            for child_node in ast.iter_child_nodes(parent_node)
        }
        docstring_value_identity_set = _docstring_value_identity_set_get(module_node)
        for node in ast.walk(module_node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in docstring_value_identity_set:
                    continue
            elif not isinstance(node, ast.JoinedStr):
                continue
            source_segment = ast.get_source_segment(source, node) or ""
            if (
                "\n" not in source_segment
                or ('"""' not in source_segment and "'''" not in source_segment)
                or _is_module_name_assignment_match(module_node, node, parent_by_identity_map)
            ):
                continue
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=("multiline triple-quoted string must be one module-level constant or module variable"),
                    path=relative_path,
                )
            )
    return finding_list


def _is_module_name_assignment_match(
    module_node: ast.Module,
    node: ast.AST,
    parent_by_identity_map: Mapping[int, ast.AST],
) -> bool:
    """Return whether one string is assigned to one module-level name.

    Args:
        module_node: Parsed module.
        node: Candidate string expression.
        parent_by_identity_map: Direct parent lookup keyed by syntax identity.

    Returns:
        Whether one canonical module-level owner exists.
    """

    parent_node = parent_by_identity_map.get(id(node))
    if isinstance(parent_node, ast.Assign):
        return (
            parent_node in module_node.body
            and len(parent_node.targets) == 1
            and isinstance(parent_node.targets[0], ast.Name)
        )
    return (
        isinstance(parent_node, ast.AnnAssign)
        and parent_node in module_node.body
        and isinstance(parent_node.target, ast.Name)
    )


def main() -> int:
    """Run the multiline-string checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
