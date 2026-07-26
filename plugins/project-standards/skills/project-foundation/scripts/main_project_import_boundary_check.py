#!/usr/bin/env python3
"""Check Main project repository-local import ownership boundaries."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import main_project_python_relpath_list_get, python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_import import (
    relative_path_by_module_name_map_get,
    repository_dependency_name_set_get,
)

FORBIDDEN_LIB_DEPENDENCY_ROOT_SET = {"backend", "script"}


def _dependency_line_get(module_node: ast.Module, dependency_module_name: str) -> int:
    """Return the first import line that can own one dependency.

    Args:
        module_node: Parsed importing module.
        dependency_module_name: Canonical repository dependency module name.

    Returns:
        Best deterministic import line.
    """

    dependency_root_name = dependency_module_name.split(".", maxsplit=1)[0]
    for node in ast.walk(module_node):
        if isinstance(node, ast.Import) and any(
            alias_node.name.split(".", maxsplit=1)[0] == dependency_root_name for alias_node in node.names
        ):
            return node.lineno
        if (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.split(".", maxsplit=1)[0] == dependency_root_name
        ):
            return node.lineno
    return 1


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return Main project import-boundary findings.

    Args:
        request: Validated checker process request.

    Returns:
        Repository-local dependency findings with exact source locations.
    """

    project_root = Path(request["project_root"])
    python_relative_path_list = python_relpath_list_get(project_root, scope="all")
    relative_path_by_module_name_map = relative_path_by_module_name_map_get(python_relative_path_list)
    requested_path_set = set(request["path_list"])
    root_entrypoint_relative_path_set = {
        relative_path
        for relative_path in main_project_python_relpath_list_get(project_root, scope="all")
        if "/" not in relative_path and relative_path != "conftest.py"
    }
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in main_project_python_relpath_list_get(project_root, scope="all"):
        path = project_root / relative_path
        if relative_path not in requested_path_set or not path.is_file():
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except SyntaxError:
            continue
        for dependency_module_name in sorted(
            repository_dependency_name_set_get(
                relative_path,
                module_node,
                relative_path_by_module_name_map,
            )
        ):
            dependency_relative_path = relative_path_by_module_name_map.get(dependency_module_name)
            if dependency_relative_path is None or dependency_relative_path == relative_path:
                continue
            message: str | None = None
            if dependency_relative_path == "conftest.py" or dependency_relative_path.startswith("test/"):
                message = f"Main project code imports root test module {dependency_module_name}"
            elif dependency_relative_path.startswith("tool/"):
                message = f"Main project code imports root tool module {dependency_module_name}"
            elif dependency_relative_path in root_entrypoint_relative_path_set:
                message = f"Main project code imports root Python script {dependency_module_name}"
            elif relative_path.startswith("lib/") and dependency_relative_path.split("/", maxsplit=1)[0] in (
                FORBIDDEN_LIB_DEPENDENCY_ROOT_SET
            ):
                message = (
                    f"shared lib code imports narrower owner module {dependency_module_name} "
                    f"from {dependency_relative_path}"
                )
            if message is not None:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=_dependency_line_get(module_node, dependency_module_name),
                        message=message,
                        path=relative_path,
                    )
                )
    return finding_list


def main() -> int:
    """Run Main project import-boundary checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
