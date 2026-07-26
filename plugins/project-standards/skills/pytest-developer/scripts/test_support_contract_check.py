#!/usr/bin/env python3
"""Check root test imports, code-test placement, and conftest symbol shape."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest


def _absolute_import_name_get(import_node: ast.ImportFrom, relative_path: str) -> str | None:
    """Resolve one import-from module name inside the root test package.

    Args:
        import_node: Candidate import-from node.
        relative_path: Importing repository-relative Python path.

    Returns:
        Absolute module name, otherwise `None`.
    """

    if import_node.level == 0:
        return import_node.module
    package_part_list = list(Path(relative_path).with_suffix("").parts[:-1])
    parent_count = import_node.level - 1
    if parent_count > len(package_part_list):
        return None
    base_part_list = package_part_list[: len(package_part_list) - parent_count]
    if import_node.module:
        base_part_list.extend(import_node.module.split("."))
    return ".".join(base_part_list)


def _conftest_finding_list_get(path: Path, relative_path: str) -> list[ProjectStandardCheckerFinding]:
    """Return public non-fixture symbol findings from one conftest module.

    Args:
        path: Conftest source path.
        relative_path: Repository-relative diagnostic path.

    Returns:
        Public class and non-hook/non-fixture function findings.
    """

    syntax_tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    finding_list: list[ProjectStandardCheckerFinding] = []
    for node in syntax_tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=f"public class {node.name} is forbidden in conftest.py",
                    path=relative_path,
                )
            )
        elif isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            if node.name.startswith(("_", "pytest_")) or _is_fixture_function(node):
                continue
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=f"public function {node.name} is not a pytest hook or fixture",
                    path=relative_path,
                )
            )
    return finding_list


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return root test-support contract findings.

    Args:
        request: Validated checker process request.

    Returns:
        Test import, code-test placement, and conftest findings.
    """

    project_root = Path(request["project_root"])
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if not path.is_file():
            continue
        if relative_path.startswith("test/code/") and (path.suffix != ".py" or not path.name.startswith("test_")):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    message="root test/code/** may contain only code-test modules named test_*.py",
                    path=relative_path,
                )
            )
        if path.name == "conftest.py" and (relative_path == "conftest.py" or relative_path.startswith("test/")):
            try:
                finding_list.extend(_conftest_finding_list_get(path, relative_path))
            except SyntaxError as error:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=error.lineno or 1,
                        message="conftest.py must be valid Python",
                        path=relative_path,
                    )
                )
        if relative_path.startswith("test/") and path.suffix == ".py":
            finding_list.extend(_test_import_finding_list_get(path, relative_path))
    return finding_list


def _is_fixture_function(function_node: ast.stmt) -> bool:
    """Return whether one function has a pytest fixture decorator.

    Args:
        function_node: Candidate function definition.

    Returns:
        Whether any decorator is the fixture name or attribute.
    """

    return any(
        (isinstance(decorator, ast.Name) and decorator.id == "fixture")
        or (isinstance(decorator, ast.Attribute) and decorator.attr == "fixture")
        or (
            isinstance(decorator, ast.Call)
            and (
                (isinstance(decorator.func, ast.Name) and decorator.func.id == "fixture")
                or (isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "fixture")
            )
        )
        for decorator in function_node.decorator_list
    )


def _test_import_finding_list_get(path: Path, relative_path: str) -> list[ProjectStandardCheckerFinding]:
    """Return root test imports that bypass the shared test/lib owner.

    Args:
        path: Root test source path.
        relative_path: Repository-relative diagnostic path.

    Returns:
        Forbidden imports from root test modules outside test/lib.
    """

    try:
        syntax_tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    except SyntaxError:
        return []
    finding_list: list[ProjectStandardCheckerFinding] = []
    imported_module_by_line_map: dict[int, set[str]] = {}
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            imported_module_by_line_map.setdefault(node.lineno, set()).update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_name = _absolute_import_name_get(node, relative_path)
            if module_name:
                imported_module_by_line_map.setdefault(node.lineno, set()).add(module_name)
    for line_number, imported_module_name_set in sorted(imported_module_by_line_map.items()):
        for imported_module_name in sorted(imported_module_name_set):
            if imported_module_name == "test" or (
                imported_module_name.startswith("test.") and not imported_module_name.startswith("test.lib.")
            ):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=line_number,
                        message=(
                            f"forbidden root test import from {imported_module_name}; "
                            "shared imported test helpers must live under test/lib/**"
                        ),
                        path=relative_path,
                    )
                )
    return finding_list


def main() -> int:
    """Run the root test-support checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
