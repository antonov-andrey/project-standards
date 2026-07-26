#!/usr/bin/env python3
"""Check root-owner top-level Python symbol visibility."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.git_repository import submodule_name_by_path_map_get
from project_standards.project_scope import (
    non_legacy_non_test_python_outside_submodule_relpath_list_get,
    python_relpath_list_get,
)
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_symbol import (
    local_load_line_set_by_name_map_get,
    python_symbol_definition_by_fqn_map_get,
    python_symbol_use_path_set_by_fqn_map_get,
)


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return top-level visibility findings.

    Args:
        request: Validated checker request.

    Returns:
        Private-class, missing-demotion, and missing-promotion findings.
    """

    project_root = Path(request["project_root"])
    submodule_relative_path_list = list(submodule_name_by_path_map_get(project_root))
    full_use_relative_path_list = [
        relative_path
        for relative_path in python_relpath_list_get(project_root, scope="all")
        if not _is_under_submodule_match(relative_path, submodule_relative_path_list)
    ]
    production_use_relative_path_list = [
        relative_path
        for relative_path in full_use_relative_path_list
        if "test" not in Path(relative_path).parts and relative_path != "conftest.py"
    ]
    definition_relative_path_list = non_legacy_non_test_python_outside_submodule_relpath_list_get(
        project_root,
        scope="all",
    )
    definition_by_fqn_map = python_symbol_definition_by_fqn_map_get(
        project_root,
        definition_relative_path_list,
    )
    production_use_path_set_by_fqn_map = python_symbol_use_path_set_by_fqn_map_get(
        project_root,
        production_use_relative_path_list,
    )
    full_use_path_set_by_fqn_map = python_symbol_use_path_set_by_fqn_map_get(
        project_root,
        full_use_relative_path_list,
    )
    requested_path_set = set(request["path_list"])
    local_load_line_set_by_name_by_path_map: dict[str, dict[str, set[int]]] = {}
    finding_list: list[ProjectStandardCheckerFinding] = []
    for symbol_fqn, definition in sorted(definition_by_fqn_map.items()):
        relative_path = definition["path"]
        if relative_path not in requested_path_set:
            continue
        name = definition["name"]
        if definition["kind"] == "class" and _is_private_name_match(name):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=definition["line"],
                    message=f"private top-level class {name} is forbidden; file-local classes remain non-private",
                    path=relative_path,
                )
            )
            continue
        production_external_use_path_set = production_use_path_set_by_fqn_map.get(symbol_fqn, set()) - {relative_path}
        if _is_private_name_match(name):
            if production_external_use_path_set:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=definition["line"],
                        message=(
                            f"private {definition['kind']} {name} is used by other modules: "
                            f"{', '.join(sorted(production_external_use_path_set))}; promote it to its public owner"
                        ),
                        path=relative_path,
                    )
                )
            continue
        if definition["kind"] == "class" or production_external_use_path_set:
            continue
        if _is_direct_execution_script_match(project_root / relative_path) and name in {"args_parse", "main"}:
            continue
        full_external_use_path_set = full_use_path_set_by_fqn_map.get(symbol_fqn, set()) - {relative_path}
        if relative_path not in local_load_line_set_by_name_by_path_map:
            try:
                module_node = ast.parse(
                    (project_root / relative_path).read_text(encoding="utf-8"),
                    filename=relative_path,
                )
            except OSError, SyntaxError:
                continue
            local_load_line_set_by_name_by_path_map[relative_path] = local_load_line_set_by_name_map_get(module_node)
        local_use_line_set = {
            line
            for line in local_load_line_set_by_name_by_path_map[relative_path].get(name, set())
            if line != definition["line"]
        }
        if not local_use_line_set or full_external_use_path_set and not local_use_line_set:
            continue
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=definition["line"],
                message=f"public {definition['kind']} {name} has no real use site outside its module; make it private",
                path=relative_path,
            )
        )
    return finding_list


def _is_direct_execution_script_match(path: Path) -> bool:
    """Return whether one module contains a top-level main guard.

    Args:
        path: Candidate Python source.

    Returns:
        Whether a canonical `__main__` comparison exists at module scope.
    """

    try:
        module_node = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    except OSError, SyntaxError:
        return False
    for child_node in module_node.body:
        if not isinstance(child_node, ast.If) or not isinstance(child_node.test, ast.Compare):
            continue
        comparison_node = child_node.test
        if len(comparison_node.ops) != 1 or not isinstance(comparison_node.ops[0], ast.Eq):
            continue
        if len(comparison_node.comparators) != 1:
            continue
        value_node_list = [comparison_node.left, comparison_node.comparators[0]]
        if any(isinstance(node, ast.Name) and node.id == "__name__" for node in value_node_list) and any(
            isinstance(node, ast.Constant) and node.value == "__main__" for node in value_node_list
        ):
            return True
    return False


def _is_private_name_match(name: str) -> bool:
    """Return whether one name is private but not dunder.

    Args:
        name: Candidate name.

    Returns:
        Whether the name has one leading underscore.
    """

    return name.startswith("_") and not name.startswith("__")


def _is_under_submodule_match(relative_path: str, submodule_relative_path_list: list[str]) -> bool:
    """Return whether one path belongs to a direct submodule.

    Args:
        relative_path: Repository-relative path.
        submodule_relative_path_list: Direct submodule roots.

    Returns:
        Whether the path is at or below one submodule root.
    """

    return any(
        relative_path == submodule_relative_path or relative_path.startswith(f"{submodule_relative_path}/")
        for submodule_relative_path in submodule_relative_path_list
    )


def main() -> int:
    """Run top-level visibility checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
