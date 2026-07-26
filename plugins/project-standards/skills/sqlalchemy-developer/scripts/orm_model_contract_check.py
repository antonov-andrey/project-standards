#!/usr/bin/env python3
"""Check static row ORM field, method, nullability, and naming contracts."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

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
from project_standards.python_syntax import call_name_get
from project_standards.validated_object import (
    validated_object_constructor_prevalidation_list_get,
    validated_object_field_wrapper_list_get,
)

ALLOWED_VALIDATED_OBJECT_KEY_SET = {"default_factory", "normalizer"}
COLLECTION_SUFFIX_BY_ROOT_NAME_MAP = {
    "dict": "_map",
    "list": "_list",
    "set": "_set",
}
JSON_OBJECT_BOUNDARY_SUFFIX_TUPLE = ("_payload", "_document", "_metadata", "_json")


def _collection_root_name_get(annotation_node: ast.expr) -> str | None:
    """Return one supported collection root from an annotation.

    Args:
        annotation_node: Candidate value annotation.

    Returns:
        `dict`, `list`, or `set`, otherwise `None`.
    """

    if isinstance(annotation_node, ast.Name):
        return annotation_node.id if annotation_node.id in COLLECTION_SUFFIX_BY_ROOT_NAME_MAP else None
    if isinstance(annotation_node, ast.Attribute):
        return annotation_node.attr if annotation_node.attr in COLLECTION_SUFFIX_BY_ROOT_NAME_MAP else None
    if isinstance(annotation_node, ast.Subscript):
        return _collection_root_name_get(annotation_node.value)
    if isinstance(annotation_node, ast.BinOp) and isinstance(annotation_node.op, ast.BitOr):
        left_name = _collection_root_name_get(annotation_node.left)
        right_name = _collection_root_name_get(annotation_node.right)
        return left_name or right_name
    return None


def _field_finding_list_get(
    class_node: ast.ClassDef,
    relative_path: str,
    scalar_default_name_set: set[str],
) -> list[ProjectStandardCheckerFinding]:
    """Return field declaration, order, nullability, and suffix findings.

    Args:
        class_node: Static row ORM class.
        relative_path: Repository-relative model path.
        scalar_default_name_set: Module constants proven to contain scalar literals.

    Returns:
        Static mapped-field findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    field_node_list = _field_node_list_get(class_node)
    for child_node in class_node.body:
        if not isinstance(child_node, (ast.Assign, ast.AnnAssign)):
            continue
        value_node = child_node.value
        if value_node is None or not _match_field_call(value_node):
            continue
        if isinstance(child_node, ast.AnnAssign) and isinstance(child_node.target, ast.Name):
            continue
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=child_node.lineno,
                message=f"{class_node.name} mapped fields must use Mapped[...] annotated assignments",
                path=relative_path,
            )
        )
    field_name_list = [field_node.target.id for field_node in field_node_list]
    if field_name_list != sorted(field_name_list):
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=field_node_list[0].lineno,
                message=f"mapped column declarations must be alphabetical: found {field_name_list!r}",
                path=relative_path,
            )
        )
    for field_node in field_node_list:
        field_name = field_node.target.id
        if _mapped_value_annotation_get(field_node.annotation) is None:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=field_node.lineno,
                    message=f"{class_node.name}.{field_name} must use one Mapped[...] annotation",
                    path=relative_path,
                )
            )
            continue
        call_node = field_node.value
        if not isinstance(call_node, ast.Call):
            continue
        finding_list.extend(
            _mapped_column_default_finding_list_get(
                call_node,
                class_node.name,
                field_name,
                relative_path,
                scalar_default_name_set,
            )
        )
        nullable_value = _literal_keyword_value_get(call_node, "nullable")
        if isinstance(nullable_value, bool) and nullable_value != _is_annotation_nullable(field_node.annotation):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=field_node.lineno,
                    message=(
                        f"{class_node.name}.{field_name} annotation nullability does not match "
                        f"mapped_column(nullable={nullable_value!r})"
                    ),
                    path=relative_path,
                )
            )
        collection_root_name = _collection_root_name_get(_mapped_value_annotation_get(field_node.annotation))
        if collection_root_name is None:
            continue
        expected_suffix = COLLECTION_SUFFIX_BY_ROOT_NAME_MAP[collection_root_name]
        if collection_root_name != "dict" or not field_name.lstrip("_").endswith(JSON_OBJECT_BOUNDARY_SUFFIX_TUPLE):
            if not field_name.endswith(expected_suffix):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=field_node.lineno,
                        message=(
                            f"field {field_name} annotated as {collection_root_name}[...] "
                            f"must end with {expected_suffix}"
                        ),
                        path=relative_path,
                    )
                )
        if call_node.args and isinstance(call_node.args[0], ast.Constant) and isinstance(call_node.args[0].value, str):
            column_name = call_node.args[0].value
            if not column_name.endswith(expected_suffix):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=field_node.lineno,
                        message=(
                            f"backing column {column_name} for {field_name} annotated as "
                            f"{collection_root_name}[...] must end with {expected_suffix}"
                        ),
                        path=relative_path,
                    )
                )
    return finding_list


def _field_node_list_get(class_node: ast.ClassDef) -> list[ast.AnnAssign]:
    """Return direct mapped-column field nodes.

    Args:
        class_node: Candidate row ORM class.

    Returns:
        Direct typed column assignments in source order.
    """

    return [
        child_node
        for child_node in class_node.body
        if isinstance(child_node, ast.AnnAssign)
        and isinstance(child_node.target, ast.Name)
        and _match_field_call(child_node.value)
    ]


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return static ORM model contract findings.

    Args:
        request: Validated checker process request.

    Returns:
        Findings across all current model_sqlalchemy row modules.
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
    field_name_set_by_fqn_map = _orm_field_name_set_by_fqn_map_get(
        base_fqn_set_by_fqn_map,
        class_node_by_fqn_map,
        orm_class_fqn_set,
    )
    constructor_target_fqn_by_import_fqn_map = {
        import_fqn: target_fqn
        for import_fqn, target_fqn in python_class_target_fqn_by_import_fqn_map_get(
            class_node_by_fqn_map,
            project_root,
            relative_path_list,
        ).items()
        if target_fqn in row_class_fqn_set
    }
    requested_path_set = set(request["path_list"])
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in relative_path_list:
        path = project_root / relative_path
        if relative_path not in requested_path_set or not path.is_file():
            continue
        try:
            syntax_tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        except SyntaxError as error:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=error.lineno or 1,
                    message="ORM owner module must be valid Python",
                    path=relative_path,
                )
            )
            continue
        for prevalidation in validated_object_constructor_prevalidation_list_get(
            constructor_target_fqn_by_import_fqn_map,
            syntax_tree,
            relative_path,
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=prevalidation["line"],
                    message=(
                        f"{prevalidation['target_fqn']} constructor receives hidden coercion, "
                        "normalization, or fallback logic"
                    ),
                    path=relative_path,
                )
            )
        if "model_sqlalchemy" not in Path(relative_path).parts:
            continue
        finding_list.extend(_validated_object_metadata_finding_list_get(syntax_tree, relative_path))
        for node in ast.walk(syntax_tree):
            if isinstance(node, ast.Call) and call_name_get(node) in {"Column", "ForeignKey"}:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=node.lineno,
                        message=(
                            "legacy Column(...) declarations are forbidden"
                            if call_name_get(node) == "Column"
                            else "ForeignKey constraints are forbidden in governed ORM models"
                        ),
                        path=relative_path,
                    )
                )
        module_name = module_name_get(relative_path)
        for class_node in syntax_tree.body:
            if not isinstance(class_node, ast.ClassDef) or f"{module_name}.{class_node.name}" not in row_class_fqn_set:
                continue
            finding_list.extend(
                _field_finding_list_get(
                    class_node,
                    relative_path,
                    _scalar_default_name_set_get(syntax_tree),
                )
            )
            finding_list.extend(_method_finding_list_get(class_node, relative_path))
            finding_list.extend(
                _validated_object_finding_list_get(
                    class_node,
                    field_name_set_by_fqn_map[f"{module_name}.{class_node.name}"],
                    syntax_tree,
                    relative_path,
                )
            )
            if not _match_strict_validation_opt_in(class_node):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=class_node.lineno,
                        message=f"{class_node.name} must declare __orm_validation_enabled__ = True",
                        path=relative_path,
                    )
                )
    return finding_list


def _is_annotation_nullable(annotation_node: ast.expr) -> bool:
    """Return whether one Mapped field annotation contains `None`.

    Args:
        annotation_node: Candidate field annotation.

    Returns:
        Whether the canonical mapped value is optional.
    """

    return _mapped_value_annotation_get(annotation_node) is not None and "None" in ast.unparse(annotation_node)


def _literal_keyword_value_get(call_node: ast.Call, keyword_name: str) -> object:
    """Return one literal keyword value.

    Args:
        call_node: Candidate call expression.
        keyword_name: Requested keyword name.

    Returns:
        Literal value, otherwise `None`.
    """

    return next(
        (
            keyword_node.value.value
            for keyword_node in call_node.keywords
            if keyword_node.arg == keyword_name and isinstance(keyword_node.value, ast.Constant)
        ),
        None,
    )


def _mapped_column_default_finding_list_get(
    call_node: ast.Call,
    class_name: str,
    field_name: str,
    relative_path: str,
    scalar_default_name_set: set[str],
) -> list[ProjectStandardCheckerFinding]:
    """Return invalid direct mapped-column default findings.

    Args:
        call_node: Mapped column or canonical column-factory call.
        class_name: Declaring row class name.
        field_name: Declared mapped field name.
        relative_path: Repository-relative model path.
        scalar_default_name_set: Module constants proven to contain scalar literals.

    Returns:
        Callable, non-scalar, and invalid default-factory findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    for keyword_node in call_node.keywords:
        if keyword_node.arg == "default" and not (
            isinstance(keyword_node.value, ast.Constant)
            or (isinstance(keyword_node.value, ast.Name) and keyword_node.value.id in scalar_default_name_set)
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=keyword_node.value.lineno,
                    message=f"{class_name}.{field_name} default must be one scalar literal",
                    path=relative_path,
                )
            )
        elif keyword_node.arg == "default_factory" and not _match_no_arg_callable_expression(keyword_node.value):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=keyword_node.value.lineno,
                    message=f"{class_name}.{field_name} default_factory must be no-arg invocable",
                    path=relative_path,
                )
            )
    return finding_list


def _mapped_value_annotation_get(annotation_node: ast.expr) -> ast.expr | None:
    """Return the value annotation inside one Mapped[...] declaration.

    Args:
        annotation_node: Candidate field annotation.

    Returns:
        Mapped value syntax, otherwise `None`.
    """

    return (
        annotation_node.slice
        if isinstance(annotation_node, ast.Subscript) and call_name_get(annotation_node.value) == "Mapped"
        else None
    )


def _match_alternative_constructor(method_node: ast.FunctionDef, class_name: str) -> bool:
    """Return whether one classmethod constructs its declaring row model.

    Args:
        method_node: Candidate classmethod definition.
        class_name: Declaring row class name.

    Returns:
        Whether every return constructs `cls` or the same class directly.
    """

    argument_node_list = [*method_node.args.posonlyargs, *method_node.args.args]
    if not argument_node_list or argument_node_list[0].arg != "cls" or not method_node.name.startswith("from_"):
        return False
    return_node_list = [node for node in ast.walk(method_node) if isinstance(node, ast.Return)]
    if not return_node_list:
        return False
    for return_node in return_node_list:
        if return_node.value is None or not isinstance(return_node.value, ast.Call):
            return False
        if not isinstance(return_node.value.func, ast.Name) or return_node.value.func.id not in {"cls", class_name}:
            return False
    return True


def _match_field_call(value_node: ast.expr | None) -> bool:
    """Return whether one assignment declares a mapped column.

    Args:
        value_node: Candidate annotated-assignment value.

    Returns:
        Whether the value is `mapped_column` or one shared column factory.
    """

    call_name = call_name_get(value_node) if value_node is not None else None
    return call_name == "mapped_column" or bool(call_name and call_name.endswith("_column_get"))


def _match_no_arg_callable_expression(expression_node: ast.expr) -> bool:
    """Return whether one expression can denote a no-argument callable.

    Args:
        expression_node: Candidate callable expression.

    Returns:
        Whether the static shape is a callable reference or a compatible lambda.
    """

    if isinstance(expression_node, (ast.Attribute, ast.Name)):
        return True
    if not isinstance(expression_node, ast.Lambda):
        return False
    positional_argument_count = len(expression_node.args.posonlyargs) + len(expression_node.args.args)
    required_positional_argument_count = positional_argument_count - len(expression_node.args.defaults)
    required_keyword_argument_count = sum(default_node is None for default_node in expression_node.args.kw_defaults)
    return required_positional_argument_count == 0 and required_keyword_argument_count == 0


def _match_strict_validation_opt_in(class_node: ast.ClassDef) -> bool:
    """Return whether one row explicitly enables strict ORM validation.

    Args:
        class_node: Static row ORM class.

    Returns:
        Whether the exact true opt-in assignment exists.
    """

    return any(
        isinstance(child_node, ast.Assign)
        and len(child_node.targets) == 1
        and isinstance(child_node.targets[0], ast.Name)
        and child_node.targets[0].id == "__orm_validation_enabled__"
        and isinstance(child_node.value, ast.Constant)
        and child_node.value.value is True
        for child_node in class_node.body
    )


def _match_table_name(class_node: ast.ClassDef) -> bool:
    """Return whether one class declares a table name.

    Args:
        class_node: Candidate ORM class.

    Returns:
        Whether the class owns one persisted table.
    """

    return any(
        isinstance(child_node, (ast.Assign, ast.AnnAssign))
        and (
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
        )
        for child_node in class_node.body
    )


def _method_finding_list_get(
    class_node: ast.ClassDef,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return forbidden row method binding findings.

    Args:
        class_node: Static row ORM class.
        relative_path: Repository-relative model path.

    Returns:
        Staticmethod and invalid classmethod findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    for method_node in class_node.body:
        if not isinstance(method_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        decorator_name_set = {
            decorator_name
            for decorator_node in method_node.decorator_list
            if (decorator_name := call_name_get(decorator_node)) is not None
        }
        if "staticmethod" in decorator_name_set:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=method_node.lineno,
                    message=f"{class_node.name}.{method_node.name} must not be a staticmethod",
                    path=relative_path,
                )
            )
        if "classmethod" in decorator_name_set and (
            not isinstance(method_node, ast.FunctionDef)
            or not _match_alternative_constructor(method_node, class_node.name)
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=method_node.lineno,
                    message=f"{class_node.name}.{method_node.name} is not one valid alternative constructor",
                    path=relative_path,
                )
            )
    return finding_list


def _orm_field_name_set_by_fqn_map_get(
    base_fqn_set_by_fqn_map: Mapping[str, set[str]],
    class_node_by_fqn_map: dict[str, ast.ClassDef],
    orm_class_fqn_set: set[str],
) -> dict[str, set[str]]:
    """Return direct and inherited mapped fields keyed by ORM class FQN.

    Args:
        base_fqn_set_by_fqn_map: Repository-local inheritance edges.
        class_node_by_fqn_map: Repository classes keyed by FQN.
        orm_class_fqn_set: OrmBase descendant closure.

    Returns:
        Canonical mapped field-name sets.
    """

    field_name_set_by_fqn_map = {
        class_fqn: {
            field_node.target.id
            for field_node in _field_node_list_get(class_node_by_fqn_map[class_fqn])
            if isinstance(field_node.target, ast.Name)
        }
        for class_fqn in orm_class_fqn_set
    }
    changed = True
    while changed:
        changed = False
        for class_fqn in orm_class_fqn_set:
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


def _scalar_default_name_set_get(module_node: ast.Module) -> set[str]:
    """Return module names transitively bound to scalar literals.

    Args:
        module_node: Parsed model module.

    Returns:
        Names whose exact module-level value is one scalar literal.
    """

    scalar_default_name_set: set[str] = set()
    changed = True
    while changed:
        changed = False
        for child_node in module_node.body:
            if (
                not isinstance(child_node, ast.Assign)
                or len(child_node.targets) != 1
                or not isinstance(child_node.targets[0], ast.Name)
            ):
                continue
            target_name = child_node.targets[0].id
            if target_name in scalar_default_name_set:
                continue
            if isinstance(child_node.value, ast.Constant) or (
                isinstance(child_node.value, ast.Name) and child_node.value.id in scalar_default_name_set
            ):
                scalar_default_name_set.add(target_name)
                changed = True
    return scalar_default_name_set


def _validated_object_finding_list_get(
    class_node: ast.ClassDef,
    field_name_set: set[str],
    module_node: ast.Module,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return ORM validated-field ordering, override, and wrapper findings.

    Args:
        class_node: Persisted row class.
        field_name_set: Direct and inherited mapped field names.
        module_node: Parsed owning module.
        relative_path: Repository-relative model path.

    Returns:
        Static validated-object findings owned by SQLAlchemy.
    """

    field_node_list = _field_node_list_get(class_node)
    direct_field_name_set = {
        field_node.target.id for field_node in field_node_list if isinstance(field_node.target, ast.Name)
    }
    finding_list: list[ProjectStandardCheckerFinding] = []
    first_field_seen = False
    for child_node in class_node.body:
        if child_node in field_node_list:
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
        elif (
            isinstance(child_node, ast.AnnAssign)
            and isinstance(child_node.target, ast.Name)
            and child_node.target.id not in direct_field_name_set
        ):
            system_name = child_node.target.id
        if system_name is not None:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=child_node.lineno,
                    message=f"system class attribute {system_name} must precede ORM fields",
                    path=relative_path,
                )
            )
    for method_node in class_node.body:
        if not isinstance(method_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        if method_node.name in {"__init__", "__setattr__", "model_copy"}:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=method_node.lineno,
                    message=f"{class_node.name} overrides validation-sensitive {method_node.name}",
                    path=relative_path,
                )
            )
    for wrapper in validated_object_field_wrapper_list_get(
        class_node,
        field_name_set,
        module_node,
    ):
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=wrapper["line"],
                message=(
                    f"{class_node.name}.{wrapper['name']} wraps ORM field {wrapper['field_name']} "
                    f"through one {wrapper['kind']} accessor"
                ),
                path=relative_path,
            )
        )
    return finding_list


def _validated_object_metadata_finding_list_get(
    syntax_tree: ast.Module,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return unsupported validated_object metadata key findings.

    Args:
        syntax_tree: Parsed ORM owner module.
        relative_path: Repository-relative source path.

    Returns:
        Unsupported metadata findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    for node in ast.walk(syntax_tree):
        if not isinstance(node, ast.Call) or call_name_get(node) != "mapped_column":
            continue
        info_node = next((keyword.value for keyword in node.keywords if keyword.arg == "info"), None)
        if not isinstance(info_node, ast.Dict):
            continue
        for key_node, value_node in zip(info_node.keys, info_node.values, strict=True):
            if not isinstance(key_node, ast.Constant) or key_node.value != "validated_object":
                continue
            if not isinstance(value_node, ast.Dict):
                continue
            value_by_key_name_map = {
                child_key.value: child_value
                for child_key, child_value in zip(value_node.keys, value_node.values, strict=True)
                if isinstance(child_key, ast.Constant) and isinstance(child_key.value, str)
            }
            key_name_set = set(value_by_key_name_map)
            unsupported_key_name_set = key_name_set - ALLOWED_VALIDATED_OBJECT_KEY_SET
            if unsupported_key_name_set:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=node.lineno,
                        message=f"unsupported validated_object keys: {sorted(unsupported_key_name_set)!r}",
                        path=relative_path,
                    )
                )
            default_factory_node = value_by_key_name_map.get("default_factory")
            if default_factory_node is not None and not _match_no_arg_callable_expression(default_factory_node):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=default_factory_node.lineno,
                        message="validated_object default_factory must be no-arg invocable",
                        path=relative_path,
                    )
                )
    return finding_list


def main() -> int:
    """Run the static row ORM model checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
