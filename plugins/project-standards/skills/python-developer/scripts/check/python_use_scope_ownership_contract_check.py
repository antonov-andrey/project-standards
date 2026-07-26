#!/usr/bin/env python3
"""Check Python owner placement derived from real repository use scope."""

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
from project_standards.python_import import (
    module_name_get,
    relative_path_by_module_name_map_get,
    repository_dependency_name_set_get,
)
from project_standards.python_symbol import (
    python_symbol_definition_by_fqn_map_get,
    python_symbol_use_path_set_by_fqn_map_get,
)


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return owner-placement and forwarding-bridge findings.

    Args:
        request: Validated checker request.

    Returns:
        Findings derived from cross-module production use scope.
    """

    project_root = Path(request["project_root"])
    submodule_relative_path_list = list(submodule_name_by_path_map_get(project_root))
    production_use_relative_path_list = [
        relative_path
        for relative_path in python_relpath_list_get(project_root, scope="all")
        if not _is_under_submodule_match(relative_path, submodule_relative_path_list)
        and "test" not in Path(relative_path).parts
        and relative_path != "conftest.py"
    ]
    definition_relative_path_list = non_legacy_non_test_python_outside_submodule_relpath_list_get(
        project_root,
        scope="all",
    )
    definition_by_fqn_map = python_symbol_definition_by_fqn_map_get(
        project_root,
        definition_relative_path_list,
    )
    use_path_set_by_fqn_map = python_symbol_use_path_set_by_fqn_map_get(
        project_root,
        production_use_relative_path_list,
    )
    requested_path_set = set(request["path_list"])
    finding_list: list[ProjectStandardCheckerFinding] = []
    for symbol_fqn, definition in sorted(definition_by_fqn_map.items()):
        relative_path = definition["path"]
        if (
            relative_path not in requested_path_set
            or relative_path.startswith("model_sqlalchemy/")
            or _is_private_name_match(definition["name"])
        ):
            continue
        external_use_path_set = use_path_set_by_fqn_map.get(symbol_fqn, set()) - {relative_path}
        consumer_path_set_by_owner_slice_map: dict[str, set[str]] = {}
        for use_relative_path in external_use_path_set:
            owner_slice = _owner_slice_get(use_relative_path)
            if owner_slice is not None:
                consumer_path_set_by_owner_slice_map.setdefault(owner_slice, set()).add(use_relative_path)
        if not consumer_path_set_by_owner_slice_map:
            continue
        owner_slice = _owner_slice_get(relative_path)
        shared_owner_root = _shared_owner_root_get(relative_path)
        if len(consumer_path_set_by_owner_slice_map) >= 2 and shared_owner_root is None:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=definition["line"],
                    message=(
                        f"{definition['name']} is shared by owner-local slices "
                        f"{', '.join(sorted(consumer_path_set_by_owner_slice_map))}; move it to one shared owner"
                    ),
                    path=relative_path,
                )
            )
            continue
        if len(consumer_path_set_by_owner_slice_map) != 1:
            continue
        consumer_owner_slice = next(iter(consumer_path_set_by_owner_slice_map))
        if (
            len(consumer_path_set_by_owner_slice_map[consumer_owner_slice]) >= 2
            and shared_owner_root != "lib"
            and owner_slice is not None
            and owner_slice != consumer_owner_slice
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=definition["line"],
                    message=(
                        f"{definition['name']} is owned by {owner_slice} but reused by modules in "
                        f"{consumer_owner_slice}"
                    ),
                    path=relative_path,
                )
            )

    relative_path_by_module_name_map = relative_path_by_module_name_map_get(production_use_relative_path_list)
    external_import_path_set_by_shared_package_map: dict[str, set[str]] = {}
    for use_relative_path in production_use_relative_path_list:
        try:
            module_node = ast.parse(
                (project_root / use_relative_path).read_text(encoding="utf-8"),
                filename=use_relative_path,
            )
        except OSError, SyntaxError:
            continue
        for dependency_module_name in repository_dependency_name_set_get(
            use_relative_path,
            module_node,
            relative_path_by_module_name_map,
        ):
            imported_relative_path = relative_path_by_module_name_map.get(dependency_module_name)
            if imported_relative_path is None:
                continue
            shared_package = _shared_package_get(imported_relative_path)
            if shared_package is None or use_relative_path.startswith(f"{shared_package}/"):
                continue
            external_import_path_set_by_shared_package_map.setdefault(shared_package, set()).add(use_relative_path)
    for shared_package, external_import_path_set in sorted(external_import_path_set_by_shared_package_map.items()):
        consumer_path_set_by_owner_slice_map: dict[str, set[str]] = {}
        have_non_owner_local_consumer = False
        for use_relative_path in external_import_path_set:
            owner_slice = _owner_slice_get(use_relative_path)
            if owner_slice is None:
                have_non_owner_local_consumer = True
                continue
            consumer_path_set_by_owner_slice_map.setdefault(owner_slice, set()).add(use_relative_path)
        if have_non_owner_local_consumer or len(consumer_path_set_by_owner_slice_map) != 1:
            continue
        if not any(
            relative_path == shared_package or relative_path.startswith(f"{shared_package}/")
            for relative_path in requested_path_set
        ):
            continue
        consumer_owner_slice = next(iter(consumer_path_set_by_owner_slice_map))
        finding_list.append(
            ProjectStandardCheckerFinding(
                message=f"shared package is used only inside {consumer_owner_slice}; move it into that owner slice",
                path=shared_package,
            )
        )

    for relative_path in definition_relative_path_list:
        path = project_root / relative_path
        if relative_path not in requested_path_set or path.name == "__init__.py":
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except OSError, SyntaxError:
            continue
        current_module_name = module_name_get(relative_path)
        defined_name_set = {
            definition["name"] for definition in definition_by_fqn_map.values() if definition["path"] == relative_path
        }
        for child_node in module_node.body:
            if not isinstance(child_node, ast.ImportFrom) or child_node.level != 0 or not child_node.module:
                continue
            if child_node.module not in relative_path_by_module_name_map:
                continue
            for alias_node in child_node.names:
                local_name = alias_node.asname or alias_node.name
                if alias_node.name == "*" or _is_private_name_match(local_name) or local_name in defined_name_set:
                    continue
                bridge_fqn = f"{current_module_name}.{local_name}"
                consumer_path_set = use_path_set_by_fqn_map.get(bridge_fqn, set()) - {relative_path}
                if consumer_path_set:
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=child_node.lineno,
                            message=(
                                f"forwarding import bridge {local_name} from {child_node.module} is used by other "
                                f"modules: {', '.join(sorted(consumer_path_set))}"
                            ),
                            path=relative_path,
                        )
                    )
    return finding_list


def _is_private_name_match(name: str) -> bool:
    """Return whether one name is private but not dunder.

    Args:
        name: Candidate name.

    Returns:
        Whether the name uses one leading underscore.
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


def _owner_slice_get(relative_path: str) -> str | None:
    """Return the canonical owner-local slice for one Python path.

    Args:
        relative_path: Repository-relative Python path.

    Returns:
        Owner-local script or tool slice, otherwise `None`.
    """

    part_list = Path(relative_path).parts
    if len(part_list) >= 2 and part_list[0] == "script":
        return "/".join(part_list[:2])
    if part_list[:1] == ("tool",):
        return "tool"
    if len(part_list) >= 4 and part_list[:2] in {(".codex", "agents"), (".codex", "skills")}:
        if part_list[3] == "tool":
            return "/".join(part_list[:4])
    return None


def _shared_owner_root_get(relative_path: str) -> str | None:
    """Return the shared owner root for one Python path.

    Args:
        relative_path: Repository-relative Python path.

    Returns:
        Shared owner root or `None`.
    """

    part_list = Path(relative_path).parts
    if part_list[:1] == ("lib",):
        return "lib"
    if part_list[:1] == ("model_sqlalchemy",):
        return "model_sqlalchemy"
    if len(part_list) >= 2 and part_list[:2] == ("tool", "lib"):
        return "tool/lib"
    if len(part_list) >= 5 and part_list[:2] in {(".codex", "agents"), (".codex", "skills")}:
        if part_list[3:5] == ("tool", "lib"):
            return "/".join(part_list[:5])
    return None


def _shared_package_get(relative_path: str) -> str | None:
    """Return one shared `lib/<package>` root.

    Args:
        relative_path: Repository-relative Python path.

    Returns:
        Shared package root or `None`.
    """

    part_list = Path(relative_path).parts
    return "/".join(part_list[:2]) if len(part_list) >= 2 and part_list[0] == "lib" else None


def main() -> int:
    """Run use-scope ownership checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
