#!/usr/bin/env python3
"""Check reliable static SQLAlchemy session and table-bootstrap ownership rules."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import main_project_python_relpath_list_get
from project_standards.project_standard_model import (
    ProjectStandardCheckerFinding,
    ProjectStandardRequest,
    ProjectStandardSessionOpeningAliasState,
)

STALE_PROJECT_SESSION_API_NAME = "project_session" "_scope"


def _attribute_path_get(node: ast.AST) -> str | None:
    """Return the dotted path of one static expression.

    Args:
        node: Candidate name or attribute.

    Returns:
        Dotted path, otherwise `None`.
    """

    if isinstance(node, ast.Name):
        return node.id
    if not isinstance(node, ast.Attribute):
        return None
    value_path = _attribute_path_get(node.value)
    return f"{value_path}.{node.attr}" if value_path is not None else None


def _class_session_finding_list_get(
    alias_state: ProjectStandardSessionOpeningAliasState,
    class_node: ast.ClassDef,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return session or engine opening calls inside one business class.

    Args:
        alias_state: Module-local opener alias sets.
        class_node: Candidate class definition.
        relative_path: Repository-relative source path.

    Returns:
        Direct SQLAlchemy state-opening findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    for node in ast.walk(class_node):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in alias_state["direct_opener_name_set"]:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=f"class {class_node.name} opens SQLAlchemy state via {node.func.id}(...)",
                    path=relative_path,
                )
            )
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        receiver_path = _attribute_path_get(node.func.value)
        if node.func.attr == "project_session_get" and receiver_path in alias_state["project_session_module_alias_set"]:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=f"class {class_node.name} opens SQLAlchemy state via project_session_get(...)",
                    path=relative_path,
                )
            )
            continue
        if not isinstance(node.func.value, ast.Name):
            continue
        receiver_name = node.func.value.id
        if receiver_name in alias_state["sqlalchemy_module_alias_set"] and node.func.attr == "create_engine":
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=f"class {class_node.name} opens SQLAlchemy state via {receiver_name}.create_engine(...)",
                    path=relative_path,
                )
            )
        elif receiver_name in alias_state["sqlalchemy_config_alias_set"] and node.func.attr in {
            "engine_get",
            "session_get",
        }:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=(
                        f"class {class_node.name} opens SQLAlchemy state via " f"{receiver_name}.{node.func.attr}(...)"
                    ),
                    path=relative_path,
                )
            )
    return finding_list


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return SQLAlchemy session and table-bootstrap findings.

    Args:
        request: Validated checker process request.

    Returns:
        Findings from current Main project Python code and stale API references.
    """

    project_root = Path(request["project_root"])
    selected_relative_path_set = set(request["path_list"])
    main_project_relative_path_list = [
        relative_path
        for relative_path in main_project_python_relpath_list_get(project_root)
        if relative_path in selected_relative_path_set
    ]
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in main_project_relative_path_list:
        path = project_root / relative_path
        try:
            syntax_tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        except SyntaxError:
            continue
        alias_state = _session_opening_alias_state_get(syntax_tree)
        for class_node in syntax_tree.body:
            if isinstance(class_node, ast.ClassDef):
                finding_list.extend(_class_session_finding_list_get(alias_state, class_node, relative_path))
        finding_list.extend(_physical_database_name_finding_list_get(syntax_tree, relative_path))
        for node in ast.walk(syntax_tree):
            if isinstance(node, ast.ImportFrom) and node.module == "sqlalchemy":
                for alias in node.names:
                    if alias.name == "inspect":
                        finding_list.append(
                            ProjectStandardCheckerFinding(
                                line=node.lineno,
                                message="manual sqlalchemy.inspect import is forbidden in Main project code",
                                path=relative_path,
                            )
                        )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"get_table_names", "has_table"}
            ):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=node.lineno,
                        message=(
                            "manual SQLAlchemy table-inspection readiness check "
                            f"{ast.unparse(node.func)} is forbidden in Main project code"
                        ),
                        path=relative_path,
                    )
                )
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if not path.is_file():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            if STALE_PROJECT_SESSION_API_NAME in line:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=line_number,
                        message=f"stale project session API name {STALE_PROJECT_SESSION_API_NAME!r} is forbidden",
                        path=relative_path,
                    )
                )
    return finding_list


def _match_engine_url_expression(node: ast.AST) -> bool:
    """Return whether one expression accesses an engine URL.

    Args:
        node: Candidate expression.

    Returns:
        Whether direct attribute or getattr URL access exists.
    """

    return (isinstance(node, ast.Attribute) and node.attr == "url") or _match_getattr_call(node, "url")


def _match_getattr_call(node: ast.AST, attribute_name: str) -> bool:
    """Return whether one expression is getattr for a literal attribute.

    Args:
        node: Candidate call expression.
        attribute_name: Required second argument value.

    Returns:
        Whether the exact getattr shape matches.
    """

    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == attribute_name
    )


def _physical_database_name_finding_list_get(
    syntax_tree: ast.Module,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return physical database-name extraction findings.

    Args:
        syntax_tree: Parsed Main project module.
        relative_path: Repository-relative source path.

    Returns:
        Engine URL database access findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Attribute) and node.attr == "database" and _match_engine_url_expression(node.value):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message="code derives a physical database name from an engine URL",
                    path=relative_path,
                )
            )
        elif _match_getattr_call(node, "database") and _match_engine_url_expression(node.args[0]):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message="code derives a physical database name from an engine URL",
                    path=relative_path,
                )
            )
    return finding_list


def _session_opening_alias_state_get(syntax_tree: ast.Module) -> ProjectStandardSessionOpeningAliasState:
    """Return module-local names that can open SQLAlchemy state.

    Args:
        syntax_tree: Parsed Main project module.

    Returns:
        Direct call names and module/provider alias sets.
    """

    alias_state = ProjectStandardSessionOpeningAliasState(
        direct_opener_name_set={"Session", "create_engine", "project_session_get", "sessionmaker"},
        project_session_module_alias_set=set(),
        sqlalchemy_config_alias_set={"sqlalchemy_config"},
        sqlalchemy_module_alias_set={"sqlalchemy"},
    )
    for node in syntax_tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name
                if alias.name == "model_sqlalchemy":
                    alias_state["project_session_module_alias_set"].add(local_name)
                elif alias.name == "model_sqlalchemy.database":
                    alias_state["project_session_module_alias_set"].add(local_name)
                    if alias.asname is None:
                        alias_state["project_session_module_alias_set"].add("model_sqlalchemy")
                elif alias.name == "sqlalchemy":
                    alias_state["sqlalchemy_module_alias_set"].add(local_name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "model_sqlalchemy.database":
                alias_state["direct_opener_name_set"].update(
                    alias.asname or alias.name for alias in node.names if alias.name == "project_session_get"
                )
            elif node.module == "sqlalchemy.orm":
                alias_state["direct_opener_name_set"].update(
                    alias.asname or alias.name for alias in node.names if alias.name in {"Session", "sessionmaker"}
                )
            elif node.module == "sqlalchemy":
                alias_state["direct_opener_name_set"].update(
                    alias.asname or alias.name for alias in node.names if alias.name == "create_engine"
                )
            elif node.module == "config_sqlalchemy":
                alias_state["sqlalchemy_config_alias_set"].update(
                    alias.asname or alias.name for alias in node.names if alias.name == "sqlalchemy_config"
                )
    return alias_state


def main() -> int:
    """Run the SQLAlchemy session and bootstrap checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
