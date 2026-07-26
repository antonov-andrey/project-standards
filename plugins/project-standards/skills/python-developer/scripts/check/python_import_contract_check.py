#!/usr/bin/env python3
"""Check repository-local Python import placement, visibility, and acyclicity."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import (
    legacy_python_relpath_list_get,
    non_legacy_non_test_python_relpath_list_get,
    python_relpath_list_get,
)
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_import import (
    absolute_import_module_name_get,
    longest_repository_module_name_get,
    module_name_get,
    package_part_list_get,
    relative_path_by_module_name_map_get,
    repository_dependency_name_set_get,
)


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return repository-local import contract findings.

    Args:
        request: Validated checker request.

    Returns:
        Import placement, visibility, dependency, and cycle findings.
    """

    project_root = Path(request["project_root"])
    all_python_relative_path_list = python_relpath_list_get(project_root, scope="all")
    eligible_relative_path_set = set(non_legacy_non_test_python_relpath_list_get(project_root, scope="all"))
    legacy_relative_path_set = set(legacy_python_relpath_list_get(project_root, scope="all"))
    relative_path_by_module_name_map = relative_path_by_module_name_map_get(all_python_relative_path_list)
    finding_list: list[ProjectStandardCheckerFinding] = []
    module_node_by_relative_path_map: dict[str, ast.Module] = {}
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if relative_path not in eligible_relative_path_set or not path.is_file():
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except SyntaxError:
            continue
        module_node_by_relative_path_map[relative_path] = module_node
        finding_list.extend(
            _module_finding_list_get(
                legacy_relative_path_set,
                module_node,
                relative_path,
                relative_path_by_module_name_map,
            )
        )
    dependency_name_set_by_module_name_map = {
        module_name_get(relative_path): repository_dependency_name_set_get(
            relative_path,
            module_node,
            relative_path_by_module_name_map,
        )
        for relative_path, module_node in module_node_by_relative_path_map.items()
    }
    for cycle_name in ImportCycleDetector(dependency_name_set_by_module_name_map).cycle_name_list_get():
        finding_list.append(
            ProjectStandardCheckerFinding(
                message=f"repository-local import cycle: {cycle_name}",
                path=relative_path_by_module_name_map[cycle_name.split(" -> ", maxsplit=1)[0]],
            )
        )
    return finding_list


def _is_import_error_handler_match(handler_node: ast.ExceptHandler) -> bool:
    """Return whether one exception handler catches import availability errors.

    Args:
        handler_node: Candidate exception handler.

    Returns:
        Whether ImportError or ModuleNotFoundError is caught.
    """

    if handler_node.type is None:
        return False
    handler_type_node_list = (
        list(handler_node.type.elts) if isinstance(handler_node.type, ast.Tuple) else [handler_node.type]
    )
    return any(
        isinstance(handler_type_node, ast.Name)
        and handler_type_node.id in {"ImportError", "ModuleNotFoundError"}
        or isinstance(handler_type_node, ast.Attribute)
        and handler_type_node.attr in {"ImportError", "ModuleNotFoundError"}
        for handler_type_node in handler_type_node_list
    )


def _module_finding_list_get(
    legacy_relative_path_set: set[str],
    module_node: ast.Module,
    relative_path: str,
    relative_path_by_module_name_map: Mapping[str, str],
) -> list[ProjectStandardCheckerFinding]:
    """Return visibility, placement, fallback, alias, and Legacy findings.

    Args:
        legacy_relative_path_set: Complete Legacy Python path set.
        module_node: Parsed module.
        relative_path: Repository-relative source path.
        relative_path_by_module_name_map: Repository paths keyed by module name.

    Returns:
        Import-contract findings for one module.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    imported_binding_name_set = _repository_imported_binding_name_set_get(
        module_node,
        relative_path,
        relative_path_by_module_name_map,
    )
    package_part_list = package_part_list_get(relative_path)
    for node in module_node.body:
        if isinstance(node, ast.Import):
            for alias_node in node.names:
                if alias_node.asname and alias_node.asname.startswith("_"):
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=node.lineno,
                            message=f"private import alias {alias_node.asname} for module {alias_node.name}",
                            path=relative_path,
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            base_module_name = absolute_import_module_name_get(package_part_list, node)
            for alias_node in node.names:
                if alias_node.name.startswith("_") and base_module_name in relative_path_by_module_name_map:
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=node.lineno,
                            message=f"private from-import {alias_node.name} from {base_module_name}",
                            path=relative_path,
                        )
                    )
                if alias_node.asname and alias_node.asname.startswith("_"):
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=node.lineno,
                            message=f"private import alias {alias_node.asname} from {node.module}",
                            path=relative_path,
                        )
                    )
        elif (
            isinstance(node, ast.Try)
            and any(isinstance(child_node, (ast.Import, ast.ImportFrom)) for child_node in node.body)
            and any(_is_import_error_handler_match(handler_node) for handler_node in node.handlers)
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message="import fallback try/except",
                    path=relative_path,
                )
            )
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and not node.targets[0].id.startswith("_")
        ):
            target_name = node.targets[0].id
            if isinstance(node.value, ast.Name) and node.value.id.startswith("_"):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=node.lineno,
                        message=f"public alias {target_name} assigned from private name {node.value.id}",
                        path=relative_path,
                    )
                )
            elif (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id in imported_binding_name_set
                and node.value.attr.startswith("_")
                and not node.value.attr.startswith("__")
            ):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=node.lineno,
                        message=(
                            f"public alias {target_name} assigned from private attribute "
                            f"{node.value.value.id}.{node.value.attr}"
                        ),
                        path=relative_path,
                    )
                )
    for node in ast.walk(module_node):
        if (
            isinstance(node, ast.Attribute)
            and node.attr.startswith("_")
            and not node.attr.startswith("__")
            and isinstance(node.value, ast.Name)
            and node.value.id in imported_binding_name_set
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=f"private attribute access {node.value.id}.{node.attr}",
                    path=relative_path,
                )
            )
    nested_import_visitor = NestedImportVisitor(relative_path)
    nested_import_visitor.visit(module_node)
    finding_list.extend(nested_import_visitor.finding_list)
    for dependency_name in sorted(
        repository_dependency_name_set_get(
            relative_path,
            module_node,
            relative_path_by_module_name_map,
        )
    ):
        dependency_relative_path = relative_path_by_module_name_map.get(dependency_name)
        if dependency_relative_path in legacy_relative_path_set:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    message=(
                        f"forbidden import of Legacy module {dependency_name} from " f"{dependency_relative_path}"
                    ),
                    path=relative_path,
                )
            )
    return finding_list


def _repository_imported_binding_name_set_get(
    module_node: ast.Module,
    relative_path: str,
    relative_path_by_module_name_map: Mapping[str, str],
) -> set[str]:
    """Return local names bound from repository-owned imports.

    Args:
        module_node: Parsed module.
        relative_path: Repository-relative source path.
        relative_path_by_module_name_map: Repository paths keyed by module name.

    Returns:
        Locally bound names that resolve to repository modules or symbols.
    """

    binding_name_set: set[str] = set()
    package_part_list = package_part_list_get(relative_path)
    for node in module_node.body:
        if isinstance(node, ast.Import):
            for alias_node in node.names:
                imported_module_name = longest_repository_module_name_get(
                    alias_node.name,
                    relative_path_by_module_name_map,
                )
                if imported_module_name is not None:
                    binding_name_set.add(alias_node.asname or alias_node.name.split(".", maxsplit=1)[0])
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        base_module_name = absolute_import_module_name_get(package_part_list, node)
        if base_module_name is None:
            continue
        for alias_node in node.names:
            if alias_node.name == "*":
                continue
            imported_module_name = longest_repository_module_name_get(
                f"{base_module_name}.{alias_node.name}",
                relative_path_by_module_name_map,
            )
            if imported_module_name is not None or base_module_name in relative_path_by_module_name_map:
                binding_name_set.add(alias_node.asname or alias_node.name)
    return binding_name_set


def main() -> int:
    """Run repository-local import checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


class ImportCycleDetector:
    """Detect deterministic cycles in one repository-local module graph."""

    def __init__(self, dependency_name_set_by_module_name_map: dict[str, set[str]]) -> None:
        """Store one complete dependency graph.

        Args:
            dependency_name_set_by_module_name_map: Direct dependencies keyed by module.
        """

        self._active_module_name_list: list[str] = []
        self._cycle_text_set: set[str] = set()
        self._dependency_name_set_by_module_name_map = dependency_name_set_by_module_name_map
        self._visited_module_name_set: set[str] = set()

    def cycle_name_list_get(self) -> list[str]:
        """Return canonical cycle renderings in deterministic order.

        Returns:
            Each cycle rendered with its start node repeated at the end.
        """

        for module_name in sorted(self._dependency_name_set_by_module_name_map):
            self._walk(module_name)
        return sorted(
            f"{cycle_text} -> {cycle_text.split(' -> ', maxsplit=1)[0]}" for cycle_text in self._cycle_text_set
        )

    def _walk(self, module_name: str) -> None:
        """Walk one module and collect back-edge cycles.

        Args:
            module_name: Current module.
        """

        if module_name in self._active_module_name_list:
            start_index = self._active_module_name_list.index(module_name)
            cycle_name_list = self._active_module_name_list[start_index:]
            rotation_text_list = [
                " -> ".join(cycle_name_list[index:] + cycle_name_list[:index]) for index in range(len(cycle_name_list))
            ]
            self._cycle_text_set.add(min(rotation_text_list))
            return
        if module_name in self._visited_module_name_set:
            return
        self._visited_module_name_set.add(module_name)
        self._active_module_name_list.append(module_name)
        for dependency_name in sorted(self._dependency_name_set_by_module_name_map.get(module_name, set())):
            self._walk(dependency_name)
        self._active_module_name_list.pop()


class NestedImportVisitor(ast.NodeVisitor):
    """Collect imports below module scope except package lazy exports."""

    def __init__(self, relative_path: str) -> None:
        """Initialize lexical owner stacks.

        Args:
            relative_path: Repository-relative source path.
        """

        self._class_name_list: list[str] = []
        self._function_name_list: list[str] = []
        self._relative_path = relative_path
        self.finding_list: list[ProjectStandardCheckerFinding] = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track one nested async callable owner.

        Args:
            node: Candidate async function.
        """

        self._function_name_list.append(node.name)
        self.generic_visit(node)
        self._function_name_list.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track one nested class owner.

        Args:
            node: Candidate class.
        """

        self._class_name_list.append(node.name)
        self.generic_visit(node)
        self._class_name_list.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track one nested callable owner.

        Args:
            node: Candidate function.
        """

        self._function_name_list.append(node.name)
        self.generic_visit(node)
        self._function_name_list.pop()

    def visit_Import(self, node: ast.Import) -> None:
        """Record one plain import below module scope.

        Args:
            node: Candidate import.
        """

        self._finding_append(node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Record one from-import below module scope.

        Args:
            node: Candidate from-import.
        """

        self._finding_append(node)
        self.generic_visit(node)

    def _finding_append(self, node: ast.stmt) -> None:
        """Append one nested-import finding outside the lazy-export exception.

        Args:
            node: Candidate import statement.
        """

        if not self._function_name_list:
            return
        if self._relative_path.endswith("__init__.py") and self._function_name_list[-1] == "__getattr__":
            return
        owner_name_list = [*self._class_name_list, self._function_name_list[-1]]
        self.finding_list.append(
            ProjectStandardCheckerFinding(
                line=node.lineno,
                message=f"non-module import inside {'.'.join(owner_name_list)}",
                path=self._relative_path,
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
