#!/usr/bin/env python3
"""Check literal Python package export declarations and bound names."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest


def _bound_name_set_get(module_node: ast.Module) -> set[str]:
    """Return top-level names bound by definitions, imports, and assignments.

    Args:
        module_node: Parsed module.

    Returns:
        Names available directly from the module surface.
    """

    bound_name_set: set[str] = set()
    for child_node in module_node.body:
        if isinstance(child_node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef)):
            bound_name_set.add(child_node.name)
        elif isinstance(child_node, ast.Import):
            bound_name_set.update(
                alias_node.asname or alias_node.name.split(".", maxsplit=1)[0] for alias_node in child_node.names
            )
        elif isinstance(child_node, ast.ImportFrom):
            bound_name_set.update(
                alias_node.asname or alias_node.name for alias_node in child_node.names if alias_node.name != "*"
            )
        elif isinstance(child_node, ast.Assign):
            bound_name_set.update(
                target_node.id for target_node in child_node.targets if isinstance(target_node, ast.Name)
            )
        elif isinstance(child_node, ast.AnnAssign) and isinstance(child_node.target, ast.Name):
            bound_name_set.add(child_node.target.id)
    return bound_name_set


def _declared_export_node_get(module_node: ast.Module) -> ast.stmt | None:
    """Return the module-level `__all__` assignment when present.

    Args:
        module_node: Parsed module.

    Returns:
        Assignment node or `None`.
    """

    for child_node in module_node.body:
        if isinstance(child_node, ast.Assign) and any(
            isinstance(target_node, ast.Name) and target_node.id == "__all__" for target_node in child_node.targets
        ):
            return child_node
        if (
            isinstance(child_node, ast.AnnAssign)
            and isinstance(child_node.target, ast.Name)
            and child_node.target.id == "__all__"
        ):
            return child_node
    return None


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return invalid literal export-surface findings.

    Args:
        request: Validated checker request.

    Returns:
        Findings for malformed, duplicate, or unavailable `__all__` names.
    """

    project_root = Path(request["project_root"])
    eligible_relative_path_set = set(non_legacy_non_test_python_relpath_list_get(project_root, scope="all"))
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if relative_path not in eligible_relative_path_set or not path.is_file():
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except SyntaxError:
            continue
        export_node = _declared_export_node_get(module_node)
        if export_node is None:
            continue
        try:
            export_value = ast.literal_eval(export_node.value)
        except TypeError, ValueError:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=export_node.lineno,
                    message="__all__ must be one literal list or tuple of exported names",
                    path=relative_path,
                )
            )
            continue
        if not isinstance(export_value, (list, tuple)) or any(
            not isinstance(export_name, str) for export_name in export_value
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=export_node.lineno,
                    message="__all__ must contain only literal string names",
                    path=relative_path,
                )
            )
            continue
        duplicate_export_name_list = sorted(
            {export_name for export_name in export_value if export_value.count(export_name) > 1}
        )
        if duplicate_export_name_list:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=export_node.lineno,
                    message=f"__all__ contains duplicate names: {', '.join(duplicate_export_name_list)}",
                    path=relative_path,
                )
            )
        bound_name_set = _bound_name_set_get(module_node)
        if "__getattr__" in bound_name_set:
            continue
        missing_export_name_list = sorted(set(export_value) - bound_name_set)
        if missing_export_name_list:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=export_node.lineno,
                    message=f"__all__ names are not bound by the module: {', '.join(missing_export_name_list)}",
                    path=relative_path,
                )
            )
    return finding_list


def main() -> int:
    """Run package-export checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
