#!/usr/bin/env python3
"""Check one project's opt-in reusable ORM field and index family."""

from __future__ import annotations

import ast
from collections.abc import Mapping
import json
from pathlib import Path
import sys
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_outside_submodule_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_class import (
    python_class_base_fqn_set_by_fqn_map_get,
    python_class_base_name_set_by_fqn_map_get,
    python_class_descendant_fqn_set_get,
    python_class_node_by_fqn_map_get,
)
from project_standards.python_import import module_name_get
from project_standards.python_syntax import call_name_get


def _class_fqn_by_relative_path_map_get(
    class_node_by_fqn_map: dict[str, ast.ClassDef],
) -> dict[str, set[str]]:
    """Return class FQNs keyed by repository-relative defining module path.

    Args:
        class_node_by_fqn_map: Repository classes keyed by FQN.

    Returns:
        Class FQN sets keyed by normalized Python path.
    """

    class_fqn_by_relative_path_map: dict[str, set[str]] = {}
    for class_fqn in class_node_by_fqn_map:
        module_name = class_fqn.rsplit(".", maxsplit=1)[0]
        relative_path = f"{module_name.replace('.', '/')}.py"
        if relative_path.endswith("/__init__.py"):
            relative_path = relative_path.removesuffix("/__init__.py") + "/__init__.py"
        class_fqn_by_relative_path_map.setdefault(relative_path, set()).add(class_fqn)
    return class_fqn_by_relative_path_map


def _field_name_by_factory_name_map_get(
    module_node_by_relative_path_map: Mapping[str, ast.Module],
) -> StandardFieldFactoryScanResult:
    """Return standard field names keyed by their canonical factory names.

    Args:
        module_node_by_relative_path_map: Parsed root Main project modules.

    Returns:
        Factory-to-field map and duplicate-family findings.
    """

    field_name_by_factory_name_map: dict[str, str] = {}
    field_owner_by_name_map: dict[str, StandardFieldOwner] = {}
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path, module_node in module_node_by_relative_path_map.items():
        if not relative_path.startswith("lib/model_sqlalchemy/"):
            continue
        for child_node in module_node.body:
            if (
                not isinstance(child_node, (ast.AsyncFunctionDef, ast.FunctionDef))
                or not child_node.name.startswith("model_")
                or not child_node.name.endswith("_column_get")
            ):
                continue
            field_name = child_node.name.removeprefix("model_").removesuffix("_column_get")
            previous_owner = field_owner_by_name_map.get(field_name)
            if previous_owner is not None:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=child_node.lineno,
                        message=(
                            f"standard field {field_name} has duplicate factories in "
                            f"{previous_owner['path']}:{previous_owner['line']} and {relative_path}"
                        ),
                        path=relative_path,
                    )
                )
                continue
            field_owner_by_name_map[field_name] = StandardFieldOwner(
                line=child_node.lineno,
                path=relative_path,
            )
            field_name_by_factory_name_map[child_node.name] = field_name
    return StandardFieldFactoryScanResult(
        field_name_by_factory_name_map=field_name_by_factory_name_map,
        finding_list=finding_list,
    )


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return reusable standard ORM field and index findings.

    Args:
        request: Validated checker process request.

    Returns:
        Findings for the project's opt-in standard field family.
    """

    project_root = Path(request["project_root"])
    relative_path_list = non_legacy_non_test_python_outside_submodule_relpath_list_get(project_root, scope="all")
    module_node_by_relative_path_map: dict[str, ast.Module] = {}
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in relative_path_list:
        path = project_root / relative_path
        try:
            module_node_by_relative_path_map[relative_path] = ast.parse(
                path.read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except SyntaxError as error:
            if relative_path in request["path_list"]:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=error.lineno or 1,
                        message="standard ORM contract owner must be valid Python",
                        path=relative_path,
                    )
                )
    factory_scan_result = _field_name_by_factory_name_map_get(module_node_by_relative_path_map)
    field_name_by_factory_name_map = factory_scan_result["field_name_by_factory_name_map"]
    finding_list.extend(factory_scan_result["finding_list"])
    if not field_name_by_factory_name_map:
        return finding_list
    standard_field_name_set = set(field_name_by_factory_name_map.values())
    factory_name_by_field_name_map = {
        field_name: factory_name for factory_name, field_name in field_name_by_factory_name_map.items()
    }
    class_node_by_fqn_map = python_class_node_by_fqn_map_get(project_root, relative_path_list)
    base_fqn_set_by_fqn_map = python_class_base_fqn_set_by_fqn_map_get(
        class_node_by_fqn_map,
        project_root,
        relative_path_list,
    )
    base_name_set_by_fqn_map = python_class_base_name_set_by_fqn_map_get(class_node_by_fqn_map)
    orm_class_fqn_set = python_class_descendant_fqn_set_get(
        base_fqn_set_by_fqn_map,
        {
            class_fqn
            for class_fqn, base_name_set in base_name_set_by_fqn_map.items()
            if "OrmBase" in base_name_set or class_fqn.endswith(".OrmBase")
        },
    )
    row_class_fqn_set = {
        class_fqn for class_fqn in orm_class_fqn_set if _match_table_name(class_node_by_fqn_map[class_fqn])
    }
    standard_base_fqn_set = {
        class_fqn
        for class_fqn in orm_class_fqn_set - row_class_fqn_set
        if class_fqn.startswith("lib.model_sqlalchemy.") and not class_fqn.endswith(".OrmBase")
    }
    standard_row_class_fqn_set = python_class_descendant_fqn_set_get(
        base_fqn_set_by_fqn_map,
        standard_base_fqn_set,
    )
    class_fqn_by_relative_path_map = _class_fqn_by_relative_path_map_get(class_node_by_fqn_map)
    requested_path_set = set(request["path_list"])
    for relative_path, module_node in module_node_by_relative_path_map.items():
        if relative_path not in requested_path_set:
            continue
        finding_list.extend(
            _managed_field_finding_list_get(
                module_node,
                relative_path,
                standard_field_name_set,
            )
        )
        if relative_path.startswith("lib/model_sqlalchemy/"):
            finding_list.extend(
                _standard_owner_finding_list_get(
                    module_node,
                    relative_path,
                    standard_base_fqn_set,
                    class_fqn_by_relative_path_map.get(relative_path, set()),
                    standard_field_name_set,
                )
            )
        if not relative_path.startswith("model_sqlalchemy/"):
            continue
        for class_node in module_node.body:
            if not isinstance(class_node, ast.ClassDef):
                continue
            class_fqn = f"{module_name_get(relative_path)}.{class_node.name}"
            if class_fqn not in row_class_fqn_set:
                continue
            finding_list.extend(
                _row_finding_list_get(
                    class_fqn,
                    class_node,
                    factory_name_by_field_name_map,
                    relative_path,
                    standard_base_fqn_set,
                    standard_field_name_set,
                    standard_row_class_fqn_set,
                )
            )
    return finding_list


def _index_column_name_list_get(call_node: ast.Call) -> list[str] | None:
    """Return literal Index column names after its index name.

    Args:
        call_node: Candidate Index call.

    Returns:
        Literal column names, or `None` for a dynamic declaration.
    """

    column_name_list: list[str] = []
    for argument_node in call_node.args[1:]:
        if not isinstance(argument_node, ast.Constant) or not isinstance(argument_node.value, str):
            return None
        column_name_list.append(argument_node.value)
    return column_name_list


def _index_name_template_get(expression_node: ast.expr) -> str | None:
    """Return one static table-name f-string template.

    Args:
        expression_node: Candidate Index name expression.

    Returns:
        Template containing `{table_name}`, otherwise `None`.
    """

    if not isinstance(expression_node, ast.JoinedStr):
        return None
    part_list: list[str] = []
    for value_node in expression_node.values:
        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            part_list.append(value_node.value)
        elif (
            isinstance(value_node, ast.FormattedValue)
            and isinstance(value_node.value, ast.Name)
            and value_node.value.id == "table_name"
        ):
            part_list.append("{table_name}")
        else:
            return None
    return "".join(part_list)


def _managed_field_finding_list_get(
    module_node: ast.Module,
    relative_path: str,
    standard_field_name_set: set[str],
) -> list[ProjectStandardCheckerFinding]:
    """Return Product API managed-field ownership findings.

    Args:
        module_node: Parsed Main project module.
        relative_path: Repository-relative source path.
        standard_field_name_set: Canonical standard field family.

    Returns:
        Local-copy, subset, and ownership findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    for child_node in module_node.body:
        if (
            not isinstance(child_node, ast.Assign)
            or len(child_node.targets) != 1
            or not isinstance(child_node.targets[0], ast.Name)
        ):
            continue
        target_name = child_node.targets[0].id
        if relative_path.startswith("backend/") and target_name == "_STANDARD_FIELD_NAME_SET":
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=child_node.lineno,
                    message="backend must not copy the project standard field set",
                    path=relative_path,
                )
            )
        if target_name != "PRODUCT_API_MANAGED_FIELD_NAME_SET":
            continue
        managed_field_name_set = _string_set_get(child_node.value)
        if managed_field_name_set is None:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=child_node.lineno,
                    message="Product API managed fields must be one static string set",
                    path=relative_path,
                )
            )
        elif not managed_field_name_set < standard_field_name_set or managed_field_name_set & {"description", "name"}:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=child_node.lineno,
                    message="Product API managed fields must be a strict standard-field subset excluding name and description",
                    path=relative_path,
                )
            )
    return finding_list


def _match_table_name(class_node: ast.ClassDef) -> bool:
    """Return whether one class declares a persisted table name.

    Args:
        class_node: Candidate ORM class.

    Returns:
        Whether `__tablename__` is assigned directly.
    """

    return any(
        (
            isinstance(child_node, ast.Assign)
            and any(
                isinstance(target_node, ast.Name) and target_node.id == "__tablename__"
                for target_node in child_node.targets
            )
        )
        or (
            isinstance(child_node, ast.AnnAssign)
            and isinstance(child_node.target, ast.Name)
            and child_node.target.id == "__tablename__"
        )
        for child_node in class_node.body
    )


def _row_finding_list_get(
    class_fqn: str,
    class_node: ast.ClassDef,
    factory_name_by_field_name_map: Mapping[str, str],
    relative_path: str,
    standard_base_fqn_set: set[str],
    standard_field_name_set: set[str],
    standard_row_class_fqn_set: set[str],
) -> list[ProjectStandardCheckerFinding]:
    """Return standard field, base, lifecycle, and local-index findings.

    Args:
        class_fqn: Persisted row class FQN.
        class_node: Persisted row declaration.
        factory_name_by_field_name_map: Canonical field factories.
        relative_path: Repository-relative row module.
        standard_base_fqn_set: Reusable project ORM base FQNs.
        standard_field_name_set: Canonical standard field family.
        standard_row_class_fqn_set: Descendants of the reusable project ORM bases.

    Returns:
        Standard row contract findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    if standard_base_fqn_set and class_fqn not in standard_row_class_fqn_set:
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=class_node.lineno,
                message="root row model must inherit the shared project ORM base",
                path=relative_path,
            )
        )
    field_node_by_name_map = {
        child_node.target.id: child_node
        for child_node in class_node.body
        if isinstance(child_node, ast.AnnAssign) and isinstance(child_node.target, ast.Name)
    }
    for field_name, field_node in field_node_by_name_map.items():
        expected_factory_name = factory_name_by_field_name_map.get(field_name)
        if expected_factory_name is None:
            continue
        actual_call_name = call_name_get(field_node.value) if field_node.value is not None else None
        if actual_call_name != expected_factory_name:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=field_node.lineno,
                    message=(
                        f"{class_node.name}.{field_name} must use {expected_factory_name}, "
                        f"found {actual_call_name or 'no field call'}"
                    ),
                    path=relative_path,
                )
            )
    if {"is_deleted", "t_create", "t_update"} <= set(field_node_by_name_map):
        t_create_node = field_node_by_name_map["t_create"]
        if isinstance(t_create_node.value, ast.Call) and any(
            keyword_node.arg == "default_factory"
            and isinstance(keyword_node.value, ast.Constant)
            and keyword_node.value.value is True
            for keyword_node in t_create_node.value.keywords
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=t_create_node.lineno,
                    message="mutable lifecycle timestamps must be synchronized by the shared row construction flow",
                    path=relative_path,
                )
            )
    for node in ast.walk(class_node):
        if not isinstance(node, ast.Call):
            continue
        call_name = call_name_get(node)
        if call_name and call_name.endswith("table_arg_list_get"):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message="row-local standard table-argument generation is forbidden",
                    path=relative_path,
                )
            )
        if call_name != "Index":
            continue
        column_name_list = _index_column_name_list_get(node)
        if column_name_list and set(column_name_list) <= standard_field_name_set:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=f"standard-only index {column_name_list!r} must use the shared table contract",
                    path=relative_path,
                )
            )
    return finding_list


def _standard_index_signature_get(
    column_name_list: list[str],
    index_name_template: str,
    is_unique: bool,
) -> str:
    """Return one deterministic standard index signature.

    Args:
        column_name_list: Ordered index column names.
        index_name_template: Static table-name-aware index name.
        is_unique: Whether the index enforces uniqueness.

    Returns:
        Canonical JSON signature used for exact set comparison.
    """

    return json.dumps(
        {
            "column_name_list": column_name_list,
            "index_name_template": index_name_template,
            "is_unique": is_unique,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _standard_index_signature_set_get(function_node: ast.FunctionDef) -> set[str]:
    """Return static Index signatures from one standard table helper.

    Args:
        function_node: Canonical standard table-argument function.

    Returns:
        Index name templates, column tuples, and uniqueness flags.
    """

    signature_set: set[str] = set()
    for node in ast.walk(function_node):
        if not isinstance(node, ast.Call) or call_name_get(node) != "Index" or not node.args:
            continue
        index_name_template = _index_name_template_get(node.args[0])
        column_name_list = _index_column_name_list_get(node)
        if index_name_template is None or column_name_list is None:
            continue
        is_unique = any(
            keyword_node.arg == "unique"
            and isinstance(keyword_node.value, ast.Constant)
            and keyword_node.value.value is True
            for keyword_node in node.keywords
        )
        signature_set.add(
            _standard_index_signature_get(
                column_name_list,
                index_name_template,
                is_unique,
            )
        )
    return signature_set


def _standard_owner_finding_list_get(
    module_node: ast.Module,
    relative_path: str,
    standard_base_fqn_set: set[str],
    module_class_fqn_set: set[str],
    standard_field_name_set: set[str],
) -> list[ProjectStandardCheckerFinding]:
    """Return shared ORM base and standard-index owner findings.

    Args:
        module_node: Parsed `lib/model_sqlalchemy` module.
        relative_path: Repository-relative owner path.
        standard_base_fqn_set: Shared project ORM base FQNs.
        module_class_fqn_set: Classes defined by the current module.
        standard_field_name_set: Canonical standard field family.

    Returns:
        Shared base delegation and index-generation findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    helper_node = next(
        (
            child_node
            for child_node in module_node.body
            if isinstance(child_node, ast.FunctionDef) and child_node.name == "model_table_arg_list_get"
        ),
        None,
    )
    if helper_node is not None:
        expected_signature_set: set[str] = set()
        if {"is_deleted", "zitadel_user_id"} <= standard_field_name_set:
            expected_signature_set.update(
                {
                    _standard_index_signature_get(
                        ["zitadel_user_id"],
                        "ix_{table_name}_zitadel_user_id",
                        False,
                    ),
                    _standard_index_signature_get(
                        ["zitadel_user_id", "is_deleted"],
                        "ix_{table_name}_zitadel_user_id_is_deleted",
                        False,
                    ),
                }
            )
        if {"is_deleted", "name", "zitadel_user_id"} <= standard_field_name_set:
            expected_signature_set.add(
                _standard_index_signature_get(
                    ["zitadel_user_id", "name"],
                    "ux_{table_name}_zitadel_user_id_name",
                    True,
                )
            )
        missing_signature_set = expected_signature_set - _standard_index_signature_set_get(helper_node)
        for missing_signature in sorted(missing_signature_set):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=helper_node.lineno,
                    message=f"standard table helper is missing index signature {missing_signature!r}",
                    path=relative_path,
                )
            )
    for class_node in module_node.body:
        if not isinstance(class_node, ast.ClassDef):
            continue
        class_fqn = next(
            (candidate_fqn for candidate_fqn in module_class_fqn_set if candidate_fqn.endswith(f".{class_node.name}")),
            None,
        )
        if class_fqn not in standard_base_fqn_set:
            continue
        table_method_node = next(
            (
                child_node
                for child_node in class_node.body
                if isinstance(child_node, (ast.AsyncFunctionDef, ast.FunctionDef))
                and child_node.name == "__table_cls__"
            ),
            None,
        )
        if table_method_node is None or not any(
            isinstance(node, ast.Call) and call_name_get(node) == "model_table_arg_list_get"
            for node in ast.walk(table_method_node)
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=class_node.lineno,
                    message="shared project ORM base must delegate standard table arguments to model_table_arg_list_get",
                    path=relative_path,
                )
            )
    return finding_list


def _string_set_get(expression_node: ast.expr) -> set[str] | None:
    """Return one static string set or frozenset.

    Args:
        expression_node: Candidate set expression.

    Returns:
        String members, or `None` for a dynamic or mixed shape.
    """

    item_node_list: list[ast.expr]
    if isinstance(expression_node, ast.Set):
        item_node_list = list(expression_node.elts)
    elif (
        isinstance(expression_node, ast.Call)
        and isinstance(expression_node.func, ast.Name)
        and expression_node.func.id == "frozenset"
        and len(expression_node.args) == 1
        and not expression_node.keywords
        and isinstance(expression_node.args[0], ast.Set)
    ):
        item_node_list = list(expression_node.args[0].elts)
    else:
        return None
    if any(
        not isinstance(item_node, ast.Constant) or not isinstance(item_node.value, str) for item_node in item_node_list
    ):
        return None
    return {item_node.value for item_node in item_node_list}


def main() -> int:
    """Run the reusable project ORM field and index checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


class StandardFieldFactoryScanResult(TypedDict):
    """Store one scan of canonical standard-field factory ownership."""

    field_name_by_factory_name_map: dict[str, str]
    finding_list: list[ProjectStandardCheckerFinding]


class StandardFieldOwner(TypedDict):
    """Store one canonical standard-field owner location."""

    line: int
    path: str


if __name__ == "__main__":
    raise SystemExit(main())
