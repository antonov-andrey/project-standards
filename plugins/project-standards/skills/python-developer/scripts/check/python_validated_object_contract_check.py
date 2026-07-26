#!/usr/bin/env python3
"""Check static BaseModel and plain data-object contracts."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_class import (
    python_class_base_fqn_set_by_fqn_map_get,
    python_class_base_name_set_by_fqn_map_get,
    python_class_descendant_fqn_set_get,
    python_class_node_by_fqn_map_get,
    python_class_target_fqn_by_import_fqn_map_get,
)
from project_standards.python_import import module_name_get
from project_standards.validated_object import (
    validated_object_constructor_prevalidation_list_get,
    validated_object_field_wrapper_list_get,
    validated_object_method_statement_list_get,
    validated_object_trivial_field_getter_name_get,
    validated_object_trivial_field_setter_name_get,
)


def _class_field_name_list_get(class_node: ast.ClassDef) -> list[str]:
    """Return direct validated field names in declaration order.

    Args:
        class_node: Candidate validated class.

    Returns:
        Direct non-private, non-ClassVar annotated field names.
    """

    field_name_list: list[str] = []
    for child_node in class_node.body:
        if (
            not isinstance(child_node, ast.AnnAssign)
            or not isinstance(child_node.target, ast.Name)
            or child_node.target.id.startswith("_")
            or _is_class_var_annotation_match(child_node.annotation)
        ):
            continue
        field_name_list.append(child_node.target.id)
    return field_name_list


def _class_field_name_set_by_fqn_map_get(
    base_fqn_set_by_fqn_map: Mapping[str, set[str]],
    class_node_by_fqn_map: dict[str, ast.ClassDef],
    validated_class_fqn_set: set[str],
) -> dict[str, set[str]]:
    """Return inherited validated fields keyed by class FQN.

    Args:
        base_fqn_set_by_fqn_map: Repository inheritance edges.
        class_node_by_fqn_map: Repository class nodes.
        validated_class_fqn_set: Validated class closure.

    Returns:
        Canonical field-name sets including inherited fields.
    """

    field_name_set_by_fqn_map = {
        class_fqn: set(_class_field_name_list_get(class_node_by_fqn_map[class_fqn]))
        for class_fqn in validated_class_fqn_set
    }
    changed = True
    while changed:
        changed = False
        for class_fqn in validated_class_fqn_set:
            inherited_field_name_set = set().union(
                *(
                    field_name_set_by_fqn_map.get(base_fqn, set())
                    for base_fqn in base_fqn_set_by_fqn_map.get(class_fqn, set())
                )
            )
            if inherited_field_name_set <= field_name_set_by_fqn_map[class_fqn]:
                continue
            field_name_set_by_fqn_map[class_fqn].update(inherited_field_name_set)
            changed = True
    return field_name_set_by_fqn_map


def _class_fqn_by_path_and_name_map_get(
    class_node_by_fqn_map: dict[str, ast.ClassDef],
    relative_path_list: list[str],
) -> dict[str, str]:
    """Return class FQNs keyed by module path and local class name.

    Args:
        class_node_by_fqn_map: Repository class nodes keyed by FQN.
        relative_path_list: Python definition paths.

    Returns:
        Class FQNs keyed by `relative_path`, NUL, and local name.
    """

    relative_path_by_module_name_map = {
        module_name_get(relative_path): relative_path for relative_path in relative_path_list
    }
    class_fqn_by_path_and_name_map: dict[str, str] = {}
    for class_fqn in class_node_by_fqn_map:
        module_name, class_name = class_fqn.rsplit(".", maxsplit=1)
        relative_path = relative_path_by_module_name_map.get(module_name)
        if relative_path is not None:
            class_fqn_by_path_and_name_map[f"{relative_path}\0{class_name}"] = class_fqn
    return class_fqn_by_path_and_name_map


def _class_system_attribute_finding_list_get(
    class_node: ast.ClassDef,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return class-system attributes declared after validated fields.

    Args:
        class_node: Candidate validated class.
        relative_path: Repository-relative source path.

    Returns:
        Field-order findings.
    """

    field_name_set = set(_class_field_name_list_get(class_node))
    first_field_seen = False
    finding_list: list[ProjectStandardCheckerFinding] = []
    for child_node in class_node.body:
        if (
            isinstance(child_node, ast.AnnAssign)
            and isinstance(child_node.target, ast.Name)
            and child_node.target.id in field_name_set
        ):
            first_field_seen = True
            continue
        if not first_field_seen:
            continue
        system_name: str | None = None
        if (
            isinstance(child_node, ast.Assign)
            and len(child_node.targets) == 1
            and isinstance(child_node.targets[0], ast.Name)
        ):
            system_name = child_node.targets[0].id
        elif isinstance(child_node, ast.AnnAssign) and isinstance(child_node.target, ast.Name):
            if child_node.target.id not in field_name_set:
                system_name = child_node.target.id
        if system_name is not None:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=child_node.lineno,
                    message=f"system class attribute {system_name} must precede validated fields",
                    path=relative_path,
                )
            )
    return finding_list


def _class_validated_fqn_set_get(
    base_fqn_set_by_fqn_map: dict[str, set[str]],
    base_name_set_by_fqn_map: Mapping[str, set[str]],
) -> set[str]:
    """Return BaseModel and BaseModelStrict class FQNs.

    Args:
        base_fqn_set_by_fqn_map: Repository inheritance edges.
        base_name_set_by_fqn_map: Visible direct base tokens.

    Returns:
        Validated class closure.
    """

    seed_class_fqn_set = {
        class_fqn
        for class_fqn, base_name_set in base_name_set_by_fqn_map.items()
        if base_name_set & {"BaseModel", "BaseModelStrict"} or class_fqn.endswith(".BaseModelStrict")
    }
    return python_class_descendant_fqn_set_get(base_fqn_set_by_fqn_map, seed_class_fqn_set)


def _class_validated_strict_fqn_set_get(
    base_fqn_set_by_fqn_map: dict[str, set[str]],
    base_name_set_by_fqn_map: Mapping[str, set[str]],
) -> set[str]:
    """Return BaseModelStrict class FQNs.

    Args:
        base_fqn_set_by_fqn_map: Repository inheritance edges.
        base_name_set_by_fqn_map: Visible direct base tokens.

    Returns:
        Strict validated class closure.
    """

    seed_class_fqn_set = {
        class_fqn
        for class_fqn, base_name_set in base_name_set_by_fqn_map.items()
        if "BaseModelStrict" in base_name_set or class_fqn.endswith(".BaseModelStrict")
    }
    return python_class_descendant_fqn_set_get(base_fqn_set_by_fqn_map, seed_class_fqn_set)


def _constructor_target_fqn_by_import_fqn_map_get(
    class_node_by_fqn_map: dict[str, ast.ClassDef],
    project_root: Path,
    relative_path_list: list[str],
    validated_class_fqn_set: set[str],
) -> dict[str, str]:
    """Return validated class targets including package re-export identities.

    Args:
        class_node_by_fqn_map: Repository class nodes.
        project_root: Exact repository root.
        relative_path_list: Python definition paths.
        validated_class_fqn_set: Validated class closure.

    Returns:
        Importable constructor identities mapped to defining class FQNs.
    """

    return {
        import_fqn: target_fqn
        for import_fqn, target_fqn in python_class_target_fqn_by_import_fqn_map_get(
            class_node_by_fqn_map,
            project_root,
            relative_path_list,
        ).items()
        if target_fqn in validated_class_fqn_set
    }


def _field_wrapper_finding_list_get(
    class_fqn: str,
    class_node: ast.ClassDef,
    field_name_set: set[str],
    module_node: ast.Module,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return validated field accessor-wrapper findings.

    Args:
        class_fqn: Candidate validated class FQN.
        class_node: Candidate class node.
        field_name_set: Canonical inherited field names.
        module_node: Parsed owning module.
        relative_path: Repository-relative source path.

    Returns:
        Property, getter, and setter findings.
    """

    return [
        ProjectStandardCheckerFinding(
            line=wrapper["line"],
            message=(
                f"{class_fqn}.{wrapper['name']} wraps canonical field {wrapper['field_name']} "
                f"through one {wrapper['kind']} accessor"
            ),
            path=relative_path,
        )
        for wrapper in validated_object_field_wrapper_list_get(
            class_node,
            field_name_set,
            module_node,
        )
    ]


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return static validated-object and plain-data findings.

    Args:
        request: Validated checker request.

    Returns:
        Constructor, bypass, field, accessor, and plain-class findings.
    """

    project_root = Path(request["project_root"])
    relative_path_list = non_legacy_non_test_python_relpath_list_get(project_root, scope="all")
    class_node_by_fqn_map = python_class_node_by_fqn_map_get(project_root, relative_path_list)
    base_fqn_set_by_fqn_map = python_class_base_fqn_set_by_fqn_map_get(
        class_node_by_fqn_map,
        project_root,
        relative_path_list,
    )
    base_name_set_by_fqn_map = python_class_base_name_set_by_fqn_map_get(class_node_by_fqn_map)
    validated_class_fqn_set = _class_validated_fqn_set_get(
        base_fqn_set_by_fqn_map,
        base_name_set_by_fqn_map,
    )
    validated_strict_class_fqn_set = _class_validated_strict_fqn_set_get(
        base_fqn_set_by_fqn_map,
        base_name_set_by_fqn_map,
    )
    orm_class_fqn_set = python_class_descendant_fqn_set_get(
        base_fqn_set_by_fqn_map,
        {
            class_fqn
            for class_fqn, base_name_set in base_name_set_by_fqn_map.items()
            if "OrmBase" in base_name_set or class_fqn.endswith(".OrmBase")
        },
    )
    database_class_fqn_set = python_class_descendant_fqn_set_get(
        base_fqn_set_by_fqn_map,
        {
            class_fqn
            for class_fqn, base_name_set in base_name_set_by_fqn_map.items()
            if "Database" in base_name_set or class_fqn.endswith(".Database")
        },
    )
    field_name_set_by_fqn_map = _class_field_name_set_by_fqn_map_get(
        base_fqn_set_by_fqn_map,
        class_node_by_fqn_map,
        validated_class_fqn_set,
    )
    class_fqn_by_path_and_name_map = _class_fqn_by_path_and_name_map_get(
        class_node_by_fqn_map,
        relative_path_list,
    )
    constructor_target_fqn_by_import_fqn_map = _constructor_target_fqn_by_import_fqn_map_get(
        class_node_by_fqn_map,
        project_root,
        relative_path_list,
        validated_class_fqn_set,
    )
    requested_path_set = set(request["path_list"])
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in relative_path_list:
        path = project_root / relative_path
        if relative_path not in requested_path_set or not path.is_file():
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except SyntaxError:
            continue
        finding_list.extend(_module_bypass_finding_list_get(module_node, relative_path))
        finding_list.extend(
            _module_constructor_finding_list_get(
                constructor_target_fqn_by_import_fqn_map,
                module_node,
                relative_path,
            )
        )
        module_name = module_name_get(relative_path)
        for class_node in [node for node in module_node.body if isinstance(node, ast.ClassDef)]:
            class_fqn = class_fqn_by_path_and_name_map.get(f"{relative_path}\0{class_node.name}")
            if class_fqn is None:
                continue
            if class_fqn in validated_class_fqn_set:
                if class_fqn in validated_strict_class_fqn_set and class_node.name != "BaseModelStrict":
                    field_name_list = _class_field_name_list_get(class_node)
                    if field_name_list != sorted(field_name_list):
                        finding_list.append(
                            ProjectStandardCheckerFinding(
                                line=class_node.lineno,
                                message=(
                                    f"{class_node.name} fields are not alphabetical: " f"{', '.join(field_name_list)}"
                                ),
                                path=relative_path,
                            )
                        )
                    finding_list.extend(_class_system_attribute_finding_list_get(class_node, relative_path))
                finding_list.extend(
                    _field_wrapper_finding_list_get(
                        class_fqn,
                        class_node,
                        field_name_set_by_fqn_map[class_fqn],
                        module_node,
                        relative_path,
                    )
                )
                for method_node in class_node.body:
                    if not isinstance(method_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                        continue
                    if method_node.name == "model_copy" and not (
                        class_node.name == "BaseModelStrict" and relative_path.endswith("base_model/strict.py")
                    ):
                        finding_list.append(
                            ProjectStandardCheckerFinding(
                                line=method_node.lineno,
                                message=f"{class_node.name} overrides validation-sensitive model_copy",
                                path=relative_path,
                            )
                        )
                continue
            if class_fqn in orm_class_fqn_set or class_fqn in database_class_fqn_set:
                continue
            if "TypedDict" in base_name_set_by_fqn_map.get(class_fqn, set()):
                continue
            resolved_base_fqn_set = base_fqn_set_by_fqn_map.get(class_fqn, set())
            external_direct_base = any(
                base_name not in {"object"}
                for base_name in base_name_set_by_fqn_map.get(class_fqn, set())
                if not any(base_fqn.endswith(f".{base_name}") for base_fqn in resolved_base_fqn_set)
            )
            finding = _plain_class_data_finding_get(
                f"{module_name}.{class_node.name}",
                class_node,
                external_direct_base,
                relative_path,
            )
            if finding is not None:
                finding_list.append(finding)
    return finding_list


def _is_class_var_annotation_match(annotation_node: ast.expr) -> bool:
    """Return whether one annotation is a ClassVar contract.

    Args:
        annotation_node: Candidate field annotation.

    Returns:
        Whether its outer type is `ClassVar`.
    """

    if isinstance(annotation_node, ast.Name):
        return annotation_node.id == "ClassVar"
    if isinstance(annotation_node, ast.Subscript):
        value_node = annotation_node.value
        return (isinstance(value_node, ast.Name) and value_node.id == "ClassVar") or (
            isinstance(value_node, ast.Attribute) and value_node.attr == "ClassVar"
        )
    return False


def _match_assignment_target_dunder_dict_subscript(target_node: ast.expr) -> bool:
    """Return whether an assignment writes through `__dict__[...]`.

    Args:
        target_node: Candidate assignment target.

    Returns:
        Whether the target bypasses normal attribute assignment.
    """

    if not isinstance(target_node, ast.Subscript):
        return False
    if isinstance(target_node.value, ast.Name):
        return target_node.value.id == "__dict__"
    return isinstance(target_node.value, ast.Attribute) and target_node.value.attr == "__dict__"


def _match_export_expression(
    expression_node: ast.expr,
    stored_field_name_set: set[str],
    exported_local_name_set: set[str],
) -> bool:
    """Return whether one payload expression embeds stored field state.

    Args:
        expression_node: Candidate payload expression.
        stored_field_name_set: Fields stored by the class.
        exported_local_name_set: Locals already known to contain stored state.

    Returns:
        Whether the expression carries stored state in an export shape.
    """

    if isinstance(expression_node, ast.Name):
        return expression_node.id in exported_local_name_set
    if (
        isinstance(expression_node, ast.Attribute)
        and isinstance(expression_node.value, ast.Name)
        and expression_node.value.id == "self"
        and expression_node.attr in stored_field_name_set
    ):
        return True
    if isinstance(expression_node, ast.Dict):
        return any(
            child_node is not None
            and _match_export_expression(
                child_node,
                stored_field_name_set,
                exported_local_name_set,
            )
            for child_node in [*expression_node.keys, *expression_node.values]
        )
    if isinstance(expression_node, (ast.List, ast.Set, ast.Tuple)):
        return any(
            _match_export_expression(
                child_node,
                stored_field_name_set,
                exported_local_name_set,
            )
            for child_node in expression_node.elts
        )
    if not isinstance(expression_node, ast.Call):
        return False
    if isinstance(expression_node.func, ast.Name) and expression_node.func.id in {"dict", "list", "set", "tuple"}:
        return any(
            _match_export_expression(
                child_node,
                stored_field_name_set,
                exported_local_name_set,
            )
            for child_node in [
                *expression_node.args,
                *(keyword_node.value for keyword_node in expression_node.keywords),
            ]
        )
    return (
        isinstance(expression_node.func, ast.Attribute)
        and expression_node.func.attr in {"dump", "export", "model_dump", "payload_get", "snapshot"}
        and isinstance(expression_node.func.value, ast.Attribute)
        and isinstance(expression_node.func.value.value, ast.Name)
        and expression_node.func.value.value.id == "self"
        and expression_node.func.value.attr in stored_field_name_set
    )


def _match_export_shape(
    expression_node: ast.expr,
    stored_field_name_set: set[str],
    exported_local_name_set: set[str],
) -> bool:
    """Return whether one expression directly exports stored state.

    Args:
        expression_node: Candidate export expression.
        stored_field_name_set: Fields stored by the class.
        exported_local_name_set: Locals already known to contain stored state.

    Returns:
        Whether the expression has one canonical state-export shape.
    """

    if _match_export_expression(expression_node, stored_field_name_set, exported_local_name_set):
        return True
    if (
        isinstance(expression_node, ast.Attribute)
        and isinstance(expression_node.value, ast.Name)
        and expression_node.value.id == "self"
        and expression_node.attr == "__dict__"
    ):
        return True
    return (
        isinstance(expression_node, ast.Call)
        and isinstance(expression_node.func, ast.Name)
        and expression_node.func.id == "vars"
        and len(expression_node.args) == 1
        and isinstance(expression_node.args[0], ast.Name)
        and expression_node.args[0].id == "self"
        and not expression_node.keywords
    )


def _match_public_export(
    function_node: ast.stmt,
    stored_field_name_set: set[str],
) -> bool:
    """Return whether one public method directly exports stored state.

    Args:
        function_node: Candidate public method.
        stored_field_name_set: Fields stored by the class.

    Returns:
        Whether the method returns one direct state-export payload.
    """

    statement_list = validated_object_method_statement_list_get(function_node)
    if not statement_list:
        return False
    exported_local_name_set: set[str] = set()
    for statement_node in statement_list[:-1]:
        target_node: ast.expr | None = None
        value_node: ast.expr | None = None
        if isinstance(statement_node, ast.Assign) and len(statement_node.targets) == 1:
            target_node = statement_node.targets[0]
            value_node = statement_node.value
        elif isinstance(statement_node, ast.AnnAssign):
            target_node = statement_node.target
            value_node = statement_node.value
        if (
            value_node is None
            or not isinstance(target_node, ast.Name)
            or not _match_export_shape(value_node, stored_field_name_set, exported_local_name_set)
        ):
            return False
        exported_local_name_set.add(target_node.id)
    final_statement_node = statement_list[-1]
    return (
        isinstance(final_statement_node, ast.Return)
        and final_statement_node.value is not None
        and _match_export_shape(
            final_statement_node.value,
            stored_field_name_set,
            exported_local_name_set,
        )
    )


def _module_bypass_finding_list_get(
    module_node: ast.Module,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return validation-bypass findings for one module.

    Args:
        module_node: Parsed module.
        relative_path: Repository-relative source path.

    Returns:
        Bypass primitive and lax-validation findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    for node in ast.walk(module_node):
        message: str | None = None
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "model_construct":
                message = "model_construct() bypasses validated-object construction"
            elif (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "object"
                and node.func.attr == "__setattr__"
            ):
                message = "object.__setattr__ bypasses assignment validation"
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "constructor"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "registry"
            ):
                message = "registry.constructor bypasses canonical construction"
            else:
                call_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                )
                if call_name in {"model_validate", "validate_json", "validate_python"} and any(
                    keyword_node.arg == "strict"
                    and isinstance(keyword_node.value, ast.Constant)
                    and keyword_node.value.value is False
                    for keyword_node in node.keywords
                ):
                    message = f"{call_name}(strict=False) opts out of strict validation"
        elif isinstance(node, ast.Assign) and any(
            _match_assignment_target_dunder_dict_subscript(target_node) for target_node in node.targets
        ):
            message = "__dict__ assignment bypasses assignment validation"
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and _match_assignment_target_dunder_dict_subscript(
            node.target
        ):
            message = "__dict__ assignment bypasses assignment validation"
        if message is not None:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=message,
                    path=relative_path,
                )
            )
    return finding_list


def _module_constructor_finding_list_get(
    constructor_target_fqn_by_import_fqn_map: dict[str, str],
    module_node: ast.Module,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return hidden constructor pre-validation findings for one module.

    Args:
        constructor_target_fqn_by_import_fqn_map: Import identities mapped to validated classes.
        module_node: Parsed module.
        relative_path: Repository-relative source path.

    Returns:
        Constructor argument findings.
    """

    return [
        ProjectStandardCheckerFinding(
            line=prevalidation["line"],
            message=(
                f"{prevalidation['target_fqn']} constructor receives hidden coercion, "
                "normalization, or fallback logic"
            ),
            path=relative_path,
        )
        for prevalidation in validated_object_constructor_prevalidation_list_get(
            constructor_target_fqn_by_import_fqn_map,
            module_node,
            relative_path,
        )
    ]


def _plain_class_data_finding_get(
    class_fqn: str,
    class_node: ast.ClassDef,
    external_direct_base: bool,
    relative_path: str,
) -> ProjectStandardCheckerFinding | None:
    """Return one plain-class public data-contract finding.

    Args:
        class_fqn: Candidate plain class FQN.
        class_node: Candidate class node.
        external_direct_base: Whether framework ownership is external.
        relative_path: Repository-relative source path.

    Returns:
        First public field/accessor/export finding or `None`.
    """

    annotated_field_name_list = [
        child_node.target.id
        for child_node in class_node.body
        if isinstance(child_node, ast.AnnAssign)
        and isinstance(child_node.target, ast.Name)
        and not child_node.target.id.startswith("_")
        and not _is_class_var_annotation_match(child_node.annotation)
    ]
    if annotated_field_name_list:
        return ProjectStandardCheckerFinding(
            line=class_node.lineno,
            message=f"plain class {class_fqn} exposes annotated field {annotated_field_name_list[0]}; use BaseModelStrict",
            path=relative_path,
        )
    stored_field_name_set: set[str] = set()
    for method_node in class_node.body:
        if not isinstance(method_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for node in ast.walk(method_node):
            target_node_list: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                target_node_list = list(node.targets)
            elif isinstance(node, ast.AnnAssign):
                target_node_list = [node.target]
            elif isinstance(node, ast.AugAssign):
                target_node_list = [node.target]
            for target_node in target_node_list:
                if (
                    isinstance(target_node, ast.Attribute)
                    and isinstance(target_node.value, ast.Name)
                    and target_node.value.id == "self"
                ):
                    stored_field_name_set.add(target_node.attr)
    public_stored_field_name_set = {name for name in stored_field_name_set if not name.startswith("_")}
    if public_stored_field_name_set and not external_direct_base:
        field_name = sorted(public_stored_field_name_set)[0]
        return ProjectStandardCheckerFinding(
            line=class_node.lineno,
            message=f"plain class {class_fqn} exposes instance field {field_name}; use BaseModelStrict",
            path=relative_path,
        )
    effective_stored_field_name_set = (
        {name for name in stored_field_name_set if name.startswith("_")}
        if external_direct_base
        else stored_field_name_set
    )
    for method_node in class_node.body:
        if not isinstance(method_node, (ast.AsyncFunctionDef, ast.FunctionDef)) or method_node.name.startswith("_"):
            continue
        getter_field_name = validated_object_trivial_field_getter_name_get(
            method_node,
            effective_stored_field_name_set,
        )
        setter_field_name = validated_object_trivial_field_setter_name_get(
            method_node,
            effective_stored_field_name_set,
        )
        if getter_field_name is not None or setter_field_name is not None:
            field_name = getter_field_name or setter_field_name or ""
            return ProjectStandardCheckerFinding(
                line=method_node.lineno,
                message=f"plain class {class_fqn} exposes field {field_name} through {method_node.name}; use BaseModelStrict",
                path=relative_path,
            )
        if _match_public_export(method_node, effective_stored_field_name_set):
            return ProjectStandardCheckerFinding(
                line=method_node.lineno,
                message=f"plain class {class_fqn} exports stored state through {method_node.name}; use BaseModelStrict",
                path=relative_path,
            )
    return None


def main() -> int:
    """Run validated-object checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
