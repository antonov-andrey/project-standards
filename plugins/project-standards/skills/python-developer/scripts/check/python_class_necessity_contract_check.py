#!/usr/bin/env python3
"""Check the mechanically certain namespace-only class anti-pattern."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_outside_submodule_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_syntax import call_name_get


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return obvious namespace-only class findings.

    Args:
        request: Validated checker request.

    Returns:
        Findings outside Legacy, tests, and direct submodules.
    """

    project_root = Path(request["project_root"])
    eligible_relative_path_set = set(
        non_legacy_non_test_python_outside_submodule_relpath_list_get(project_root, scope="all")
    )
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if relative_path not in eligible_relative_path_set or not path.is_file():
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except SyntaxError:
            continue
        for class_node in module_node.body:
            if (
                not isinstance(class_node, ast.ClassDef)
                or class_node.bases
                or class_node.decorator_list
                or not any(
                    isinstance(child_node, (ast.AsyncFunctionDef, ast.FunctionDef)) for child_node in class_node.body
                )
                or _have_instance_method(class_node)
            ):
                continue
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=class_node.lineno,
                    message=(
                        f"{class_node.name} is a namespace-only class without inheritance or instance methods; "
                        "use module-level functions instead"
                    ),
                    path=relative_path,
                )
            )
    return finding_list


def _have_instance_method(class_node: ast.ClassDef) -> bool:
    """Return whether one class declares a real instance method.

    Args:
        class_node: Candidate top-level class.

    Returns:
        Whether a non-static, non-class method receives `self`.
    """

    for child_node in class_node.body:
        if not isinstance(child_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        decorator_name_set = {
            name for decorator_node in child_node.decorator_list if (name := call_name_get(decorator_node))
        }
        if decorator_name_set & {"classmethod", "staticmethod"}:
            continue
        if child_node.args.args and child_node.args.args[0].arg == "self":
            return True
    return False


def main() -> int:
    """Run class-necessity checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
