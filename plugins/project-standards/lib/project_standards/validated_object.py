"""Resolve static validated-object constructor and field-wrapper shapes."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from project_standards.project_standard_model import (
    ProjectStandardPropertyDescriptor,
    ProjectStandardPropertyResolution,
    ProjectStandardValidatedConstructorPrevalidation,
    ProjectStandardValidatedFieldWrapper,
)
from project_standards.python_import import (
    absolute_import_module_name_get,
    module_name_get,
    package_part_list_get,
)

CONSTRUCTOR_COERCION_NAME_SET = {"bool", "dict", "float", "int", "list", "str"}
STRING_NORMALIZER_METHOD_NAME_SET = {"casefold", "lower", "lstrip", "rstrip", "strip", "upper"}


def _match_default_literal(node: ast.AST) -> bool:
    """Return whether one node is a hidden fallback-default literal.

    Args:
        node: Candidate expression.

    Returns:
        Whether the node denotes an empty or zero default.
    """

    if isinstance(node, ast.Constant) and node.value in {"", 0, 0.0}:
        return True
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)) and not node.elts:
        return True
    if isinstance(node, ast.Dict) and not node.keys:
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"dict", "list", "set"}
        and not node.args
        and not node.keywords
    )


def _match_hidden_prevalidation(expression_node: ast.expr) -> bool:
    """Return whether one constructor argument performs hidden normalization.

    Args:
        expression_node: Candidate argument expression.

    Returns:
        Whether it coerces, normalizes, or supplies a fallback default.
    """

    for node in ast.walk(expression_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in CONSTRUCTOR_COERCION_NAME_SET:
                return True
            if isinstance(node.func, ast.Attribute) and node.func.attr in STRING_NORMALIZER_METHOD_NAME_SET:
                return True
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            if any(_match_default_literal(value_node) for value_node in node.values[1:]):
                return True
    return False


def validated_object_constructor_prevalidation_list_get(
    constructor_target_fqn_by_import_fqn_map: Mapping[str, str],
    module_node: ast.Module,
    relative_path: str,
) -> list[ProjectStandardValidatedConstructorPrevalidation]:
    """Return validated constructor calls with hidden pre-validation.

    Args:
        constructor_target_fqn_by_import_fqn_map: Import identities mapped to defining classes.
        module_node: Parsed call-site module.
        relative_path: Repository-relative call-site path.

    Returns:
        Hidden pre-validation call records.
    """

    module_name = module_name_get(relative_path)
    target_fqn_by_local_name_map = {
        child_node.name: target_fqn
        for child_node in module_node.body
        if isinstance(child_node, ast.ClassDef)
        and (target_fqn := constructor_target_fqn_by_import_fqn_map.get(f"{module_name}.{child_node.name}")) is not None
    }
    module_name_by_local_name_map: dict[str, str] = {}
    for child_node in module_node.body:
        if isinstance(child_node, ast.Import):
            for alias_node in child_node.names:
                module_name_by_local_name_map[alias_node.asname or alias_node.name.split(".", maxsplit=1)[0]] = (
                    alias_node.name
                )
        elif isinstance(child_node, ast.ImportFrom):
            imported_module_name = absolute_import_module_name_get(
                package_part_list_get(relative_path),
                child_node,
            )
            if imported_module_name is None:
                continue
            for alias_node in child_node.names:
                candidate_fqn = f"{imported_module_name}.{alias_node.name}"
                target_fqn = constructor_target_fqn_by_import_fqn_map.get(candidate_fqn)
                if target_fqn is not None:
                    target_fqn_by_local_name_map[alias_node.asname or alias_node.name] = target_fqn
    prevalidation_list: list[ProjectStandardValidatedConstructorPrevalidation] = []
    for call_node in [node for node in ast.walk(module_node) if isinstance(node, ast.Call)]:
        target_fqn: str | None = None
        if isinstance(call_node.func, ast.Name):
            target_fqn = target_fqn_by_local_name_map.get(call_node.func.id)
        elif isinstance(call_node.func, ast.Attribute) and isinstance(call_node.func.value, ast.Name):
            imported_module_name = module_name_by_local_name_map.get(call_node.func.value.id)
            if imported_module_name is not None:
                target_fqn = constructor_target_fqn_by_import_fqn_map.get(
                    f"{imported_module_name}.{call_node.func.attr}"
                )
        if target_fqn is None:
            continue
        argument_node_list = [
            *call_node.args,
            *(keyword_node.value for keyword_node in call_node.keywords),
        ]
        if any(_match_hidden_prevalidation(argument_node) for argument_node in argument_node_list):
            prevalidation_list.append(
                ProjectStandardValidatedConstructorPrevalidation(
                    line=call_node.lineno,
                    target_fqn=target_fqn,
                )
            )
    return prevalidation_list


def _class_property_descriptor_list_get(
    class_node: ast.ClassDef,
    property_factory_name_set: set[str],
    builtins_module_name_set: set[str],
) -> list[ProjectStandardPropertyDescriptor]:
    """Return class-level property names, getters, and lines.

    Args:
        class_node: Candidate class.
        property_factory_name_set: Resolved property factory names.
        builtins_module_name_set: Resolved builtins module aliases.

    Returns:
        Property descriptor identities.
    """

    descriptor_list: list[ProjectStandardPropertyDescriptor] = []
    for child_node in class_node.body:
        target_node: ast.expr | None = None
        value_node: ast.expr | None = None
        if isinstance(child_node, ast.Assign) and len(child_node.targets) == 1:
            target_node = child_node.targets[0]
            value_node = child_node.value
        elif isinstance(child_node, ast.AnnAssign):
            target_node = child_node.target
            value_node = child_node.value
        if (
            not isinstance(target_node, ast.Name)
            or not isinstance(value_node, ast.Call)
            or not _match_property_factory(
                value_node.func,
                property_factory_name_set,
                builtins_module_name_set,
            )
        ):
            continue
        getter_name = value_node.args[0].id if value_node.args and isinstance(value_node.args[0], ast.Name) else None
        for keyword_node in value_node.keywords:
            if keyword_node.arg == "fget" and isinstance(keyword_node.value, ast.Name):
                getter_name = keyword_node.value.id
        descriptor_list.append(
            ProjectStandardPropertyDescriptor(
                getter_name=getter_name,
                line=child_node.lineno,
                name=target_node.id,
            )
        )
    return descriptor_list


def _match_method_property_accessor(
    method_node: ast.stmt,
    property_factory_name_set: set[str],
    builtins_module_name_set: set[str],
) -> bool:
    """Return whether one method uses property-style decorators.

    Args:
        method_node: Candidate method.
        property_factory_name_set: Resolved property factory names.
        builtins_module_name_set: Resolved builtins module aliases.

    Returns:
        Whether the method is a property accessor.
    """

    return any(
        _match_property_factory(
            decorator_node,
            property_factory_name_set,
            builtins_module_name_set,
        )
        or (isinstance(decorator_node, ast.Attribute) and decorator_node.attr in {"deleter", "setter"})
        for decorator_node in method_node.decorator_list
    )


def _match_property_factory(
    expression_node: ast.expr,
    property_factory_name_set: set[str],
    builtins_module_name_set: set[str],
) -> bool:
    """Return whether one expression resolves to the property factory.

    Args:
        expression_node: Candidate decorator or call target.
        property_factory_name_set: Resolved property factory names.
        builtins_module_name_set: Resolved builtins module aliases.

    Returns:
        Whether the expression denotes `property`.
    """

    return (isinstance(expression_node, ast.Name) and expression_node.id in property_factory_name_set) or (
        isinstance(expression_node, ast.Attribute)
        and isinstance(expression_node.value, ast.Name)
        and expression_node.value.id in builtins_module_name_set
        and expression_node.attr == "property"
    )


def _module_property_resolution_get(module_node: ast.Module) -> ProjectStandardPropertyResolution:
    """Return names that resolve to property and builtins.

    Args:
        module_node: Parsed owning module.

    Returns:
        Property factory names and builtins aliases.
    """

    property_factory_name_set = {"property"}
    builtins_module_name_set = {"builtins"}
    changed = True
    while changed:
        changed = False
        for node in module_node.body:
            if isinstance(node, ast.Import):
                for alias_node in node.names:
                    if (
                        alias_node.name == "builtins"
                        and (local_name := alias_node.asname or alias_node.name) not in builtins_module_name_set
                    ):
                        builtins_module_name_set.add(local_name)
                        changed = True
            elif isinstance(node, ast.ImportFrom) and node.module == "builtins":
                for alias_node in node.names:
                    if (
                        alias_node.name == "property"
                        and (local_name := alias_node.asname or alias_node.name) not in property_factory_name_set
                    ):
                        property_factory_name_set.add(local_name)
                        changed = True
            else:
                target_name: str | None = None
                value_node: ast.expr | None = None
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    target_name = node.targets[0].id
                    value_node = node.value
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    target_name = node.target.id
                    value_node = node.value
                if target_name is None or value_node is None:
                    continue
                if isinstance(value_node, ast.Name) and value_node.id in property_factory_name_set:
                    if target_name not in property_factory_name_set:
                        property_factory_name_set.add(target_name)
                        changed = True
                elif (
                    isinstance(value_node, ast.Attribute)
                    and isinstance(value_node.value, ast.Name)
                    and value_node.value.id in builtins_module_name_set
                    and value_node.attr == "property"
                    and target_name not in property_factory_name_set
                ):
                    property_factory_name_set.add(target_name)
                    changed = True
    return ProjectStandardPropertyResolution(
        builtins_module_name_set=builtins_module_name_set,
        property_factory_name_set=property_factory_name_set,
    )


def validated_object_field_wrapper_list_get(
    class_node: ast.ClassDef,
    field_name_set: set[str],
    module_node: ast.Module,
) -> list[ProjectStandardValidatedFieldWrapper]:
    """Return wrappers around canonical fields on one validated class.

    Args:
        class_node: Candidate validated class.
        field_name_set: Canonical direct and inherited field names.
        module_node: Parsed owning module.

    Returns:
        Property, getter, and setter wrapper records.
    """

    property_resolution = _module_property_resolution_get(module_node)
    method_node_by_name_map = {
        child_node.name: child_node
        for child_node in class_node.body
        if isinstance(child_node, (ast.AsyncFunctionDef, ast.FunctionDef))
    }
    wrapper_list: list[ProjectStandardValidatedFieldWrapper] = []
    for descriptor in _class_property_descriptor_list_get(
        class_node,
        property_resolution["property_factory_name_set"],
        property_resolution["builtins_module_name_set"],
    ):
        field_name = descriptor["name"] if descriptor["name"] in field_name_set else None
        if (
            field_name is None
            and descriptor["getter_name"] is not None
            and descriptor["getter_name"] in method_node_by_name_map
        ):
            field_name = validated_object_trivial_field_getter_name_get(
                method_node_by_name_map[descriptor["getter_name"]],
                field_name_set,
            )
        if field_name is not None:
            wrapper_list.append(
                ProjectStandardValidatedFieldWrapper(
                    field_name=field_name,
                    kind="class-level-property",
                    line=descriptor["line"],
                    name=descriptor["name"],
                )
            )
    for method_node in method_node_by_name_map.values():
        getter_field_name = validated_object_trivial_field_getter_name_get(method_node, field_name_set)
        if _match_method_property_accessor(
            method_node,
            property_resolution["property_factory_name_set"],
            property_resolution["builtins_module_name_set"],
        ):
            if getter_field_name is not None:
                wrapper_list.append(
                    ProjectStandardValidatedFieldWrapper(
                        field_name=getter_field_name,
                        kind="property",
                        line=method_node.lineno,
                        name=method_node.name,
                    )
                )
            continue
        if getter_field_name is not None:
            wrapper_list.append(
                ProjectStandardValidatedFieldWrapper(
                    field_name=getter_field_name,
                    kind="getter",
                    line=method_node.lineno,
                    name=method_node.name,
                )
            )
            continue
        setter_field_name = validated_object_trivial_field_setter_name_get(method_node, field_name_set)
        if setter_field_name is not None:
            wrapper_list.append(
                ProjectStandardValidatedFieldWrapper(
                    field_name=setter_field_name,
                    kind="setter",
                    line=method_node.lineno,
                    name=method_node.name,
                )
            )
    return wrapper_list


def validated_object_method_statement_list_get(
    function_node: ast.stmt,
) -> list[ast.stmt]:
    """Return executable method statements without the docstring.

    Args:
        function_node: Candidate method.

    Returns:
        Direct executable statements.
    """

    statement_list = list(function_node.body)
    if (
        statement_list
        and isinstance(statement_list[0], ast.Expr)
        and isinstance(statement_list[0].value, ast.Constant)
        and isinstance(statement_list[0].value.value, str)
    ):
        statement_list = statement_list[1:]
    return statement_list


def validated_object_trivial_field_getter_name_get(
    function_node: ast.stmt,
    field_name_set: set[str],
) -> str | None:
    """Return the field exposed by one trivial getter.

    Args:
        function_node: Candidate method.
        field_name_set: Canonical or stored field names.

    Returns:
        Direct field name or `None`.
    """

    statement_list = validated_object_method_statement_list_get(function_node)
    if len(statement_list) != 1 or not isinstance(statement_list[0], ast.Return):
        return None
    value_node = statement_list[0].value
    if (
        isinstance(value_node, ast.Attribute)
        and isinstance(value_node.value, ast.Name)
        and value_node.value.id == "self"
        and value_node.attr in field_name_set
    ):
        return value_node.attr
    return None


def validated_object_trivial_field_setter_name_get(
    function_node: ast.stmt,
    field_name_set: set[str],
) -> str | None:
    """Return the field assigned by one trivial setter.

    Args:
        function_node: Candidate method.
        field_name_set: Canonical or stored field names.

    Returns:
        Direct field name or `None`.
    """

    statement_list = validated_object_method_statement_list_get(function_node)
    if not statement_list or len(statement_list) > 2:
        return None
    assignment_node = statement_list[0]
    if isinstance(assignment_node, ast.Assign) and len(assignment_node.targets) == 1:
        target_node = assignment_node.targets[0]
        value_node = assignment_node.value
    elif isinstance(assignment_node, ast.AnnAssign):
        target_node = assignment_node.target
        value_node = assignment_node.value
    else:
        return None
    parameter_name_list = [
        argument_node.arg for argument_node in function_node.args.args if argument_node.arg != "self"
    ]
    if (
        value_node is None
        or len(parameter_name_list) != 1
        or not isinstance(value_node, ast.Name)
        or value_node.id != parameter_name_list[0]
        or not isinstance(target_node, ast.Attribute)
        or not isinstance(target_node.value, ast.Name)
        or target_node.value.id != "self"
        or target_node.attr not in field_name_set
    ):
        return None
    if len(statement_list) == 2 and (
        not isinstance(statement_list[1], ast.Return) or statement_list[1].value is not None
    ):
        return None
    return target_node.attr
