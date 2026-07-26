#!/usr/bin/env python3
"""Check model_sqlalchemy row-module and package-surface contracts."""

from __future__ import annotations

import ast
from pathlib import Path
import sys
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_syntax import class_base_name_set_get

PROJECT_DATABASE_EXPORT_NAME_SET = {
    "project_database_ensure",
    "project_database_list",
    "project_session_get",
}


def _all_name_list_get(module_node: ast.Module) -> list[str]:
    """Return one literal package export list.

    Args:
        module_node: Parsed package module.

    Returns:
        Literal string export names, or an empty list.
    """

    for node in module_node.body:
        value_node: ast.expr | None = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target_node, ast.Name) and target_node.id == "__all__" for target_node in node.targets
        ):
            value_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            value_node = node.value
        if value_node is None:
            continue
        try:
            value = ast.literal_eval(value_node)
        except TypeError, ValueError:
            return []
        return [item for item in value if isinstance(item, str)] if isinstance(value, (list, tuple)) else []
    return []


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return model package and row-module findings.

    Args:
        request: Validated checker process request.

    Returns:
        Static owner, export, and table-identity findings.
    """

    project_root = Path(request["project_root"])
    relative_path_list = [
        relative_path
        for relative_path in request["path_list"]
        if relative_path.startswith("model_sqlalchemy/")
        and relative_path.endswith(".py")
        and (project_root / relative_path).is_file()
    ]
    module_node_by_relative_path_map: dict[str, ast.Module] = {}
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in relative_path_list:
        try:
            module_node_by_relative_path_map[relative_path] = ast.parse(
                (project_root / relative_path).read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except SyntaxError:
            continue
    row_class_name_by_module_name_map: dict[str, str] = {}
    for relative_path, module_node in module_node_by_relative_path_map.items():
        part_tuple = Path(relative_path).parts
        if len(part_tuple) != 3 or part_tuple[-1] == "__init__.py":
            continue
        row_class_node_list = [
            node
            for node in module_node.body
            if isinstance(node, ast.ClassDef)
            and any(base_name.endswith("OrmBase") for base_name in class_base_name_set_get(node))
            and _table_name_get(node) is not None
        ]
        if len(row_class_node_list) != 1:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=1,
                    message="one ORM table module must define exactly one persisted row class",
                    path=relative_path,
                )
            )
            continue
        row_class_node = row_class_node_list[0]
        table_name = _table_name_get(row_class_node)
        if table_name != Path(relative_path).stem:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=row_class_node.lineno,
                    message=(
                        f"{row_class_node.name}.__tablename__ must equal module stem " f"{Path(relative_path).stem!r}"
                    ),
                    path=relative_path,
                )
            )
        module_name = Path(relative_path).with_suffix("").as_posix().replace("/", ".")
        row_class_name_by_module_name_map[module_name] = row_class_node.name
    row_class_name_set = set(row_class_name_by_module_name_map.values())
    for relative_path, module_node in module_node_by_relative_path_map.items():
        if not relative_path.endswith("/__init__.py") and relative_path != "model_sqlalchemy/__init__.py":
            continue
        part_tuple = Path(relative_path).parts
        all_name_list = _all_name_list_get(module_node)
        import_source_by_local_name_map = _import_source_by_local_name_map_get(module_node)
        if len(part_tuple) >= 4:
            if all_name_list:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=1,
                        message="DB support-object package must not define named exports",
                        path=relative_path,
                    )
                )
            continue
        for export_name in all_name_list:
            source = import_source_by_local_name_map.get(export_name)
            if source is None:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=1,
                        message=f"package export {export_name} must be one imported binding",
                        path=relative_path,
                    )
                )
                continue
            source_module_name = source["module_name"]
            source_name = source["name"]
            if len(part_tuple) == 3:
                expected_row_class_name = row_class_name_by_module_name_map.get(source_module_name)
                if expected_row_class_name != source_name:
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=1,
                            message=f"database package export {export_name} is not one row ORM model",
                            path=relative_path,
                        )
                    )
            elif source_module_name == "model_sqlalchemy.database":
                if source_name not in PROJECT_DATABASE_EXPORT_NAME_SET and not source_name.endswith("Database"):
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=1,
                            message=f"root package export {export_name} is not one database registry contract",
                            path=relative_path,
                        )
                    )
            elif source_name not in row_class_name_set:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=1,
                        message=f"root package export {export_name} is not one row ORM model",
                        path=relative_path,
                    )
                )
    return finding_list


def _import_source_by_local_name_map_get(module_node: ast.Module) -> dict[str, ProjectStandardImportSource]:
    """Return direct from-import sources keyed by local binding.

    Args:
        module_node: Parsed package module.

    Returns:
        Source module and source name for every direct imported binding.
    """

    source_by_local_name_map: dict[str, ProjectStandardImportSource] = {}
    for node in module_node.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 0 or node.module is None:
            continue
        for alias_node in node.names:
            if alias_node.name == "*":
                continue
            source_by_local_name_map[alias_node.asname or alias_node.name] = ProjectStandardImportSource(
                module_name=node.module,
                name=alias_node.name,
            )
    return source_by_local_name_map


def _table_name_get(class_node: ast.ClassDef) -> str | None:
    """Return one literal ORM table name.

    Args:
        class_node: Candidate row class.

    Returns:
        Literal table name, or `None`.
    """

    for node in class_node.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__tablename__"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


def main() -> int:
    """Run model package checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


class ProjectStandardImportSource(TypedDict):
    """Store one direct import source identity."""

    module_name: str
    name: str


if __name__ == "__main__":
    raise SystemExit(main())
