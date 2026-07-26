#!/usr/bin/env python3
"""Check package-local object ownership and alternative-constructor shapes."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_outside_submodule_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_import import (
    absolute_import_module_name_get,
    module_name_get,
    package_part_list_get,
    relative_path_by_module_name_map_get,
)
from project_standards.python_syntax import call_name_get


def _annotation_normalize(annotation_node: ast.expr | None) -> ast.expr | None:
    """Return a parsed annotation, including one quoted forward reference.

    Args:
        annotation_node: Candidate annotation.

    Returns:
        Parsed annotation or `None` when it is absent or malformed.
    """

    if not isinstance(annotation_node, ast.Constant) or not isinstance(annotation_node.value, str):
        return annotation_node
    try:
        return ast.parse(annotation_node.value, mode="eval").body
    except SyntaxError:
        return None


def _callable_finding_list_get(
    callable_label: str,
    class_fqn_by_local_name_map: Mapping[str, str],
    class_fqn_set: set[str],
    current_class_fqn: str | None,
    function_node: ast.stmt,
    module_name_by_local_name_map: Mapping[str, str],
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return ownership findings for one non-instance callable.

    Args:
        callable_label: Human-readable callable identity.
        class_fqn_by_local_name_map: Same-package class bindings.
        class_fqn_set: All package-local class FQNs.
        current_class_fqn: Owning class FQN for a method, otherwise `None`.
        function_node: Candidate non-instance callable.
        module_name_by_local_name_map: Same-package module bindings.
        relative_path: Repository-relative module path.

    Returns:
        Alternative-constructor and package-object ownership findings.
    """

    decorator_name_set = _decorator_name_set_get(function_node)
    returned_class_fqn_list = sorted(
        _direct_class_fqn_set_get(
            function_node.returns,
            class_fqn_by_local_name_map,
            class_fqn_set,
            module_name_by_local_name_map,
        )
    )
    finding_list: list[ProjectStandardCheckerFinding] = []
    is_alternative_constructor_name = function_node.name.startswith(("from_", "_from_"))
    if "classmethod" in decorator_name_set and is_alternative_constructor_name and current_class_fqn is not None:
        nested_class_fqn_set = _nested_class_fqn_set_get(
            function_node.returns,
            class_fqn_by_local_name_map,
            class_fqn_set,
            module_name_by_local_name_map,
        )
        if current_class_fqn in nested_class_fqn_set and current_class_fqn not in returned_class_fqn_list:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=function_node.lineno,
                    message=(
                        f"{callable_label} is named from_* or _from_* but returns "
                        f"{ast.unparse(_annotation_normalize(function_node.returns))}; alternative constructors "
                        f"must return {current_class_fqn.rsplit('.', maxsplit=1)[-1]} directly"
                    ),
                    path=relative_path,
                )
            )
            return finding_list
    if (
        "classmethod" in decorator_name_set
        and current_class_fqn is not None
        and current_class_fqn in returned_class_fqn_list
    ):
        if is_alternative_constructor_name:
            return finding_list
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=function_node.lineno,
                message=f"{callable_label} returns its owning class and must be named from_* or _from_*",
                path=relative_path,
            )
        )
        return finding_list

    parameter_class_fqn_list = _parameter_class_fqn_list_get(
        function_node,
        class_fqn_by_local_name_map,
        class_fqn_set,
        module_name_by_local_name_map,
    )
    for returned_class_fqn in returned_class_fqn_list:
        owner_guidance = (
            "move this behavior onto the returned class as from_* or _from_* @classmethod"
            if not parameter_class_fqn_list
            else (
                "resolve the real owner by moving it onto the returned class as an alternative constructor or "
                f"onto one parameter class as an instance method; parameter classes: "
                f"{', '.join(parameter_class_fqn_list)}"
            )
        )
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=function_node.lineno,
                message=f"{callable_label} returns package-local class {returned_class_fqn}; {owner_guidance}",
                path=relative_path,
            )
        )

    first_argument_node = _first_explicit_argument_get(function_node)
    if first_argument_node is None:
        return finding_list
    first_parameter_class_fqn_list = sorted(
        _direct_class_fqn_set_get(
            first_argument_node.annotation,
            class_fqn_by_local_name_map,
            class_fqn_set,
            module_name_by_local_name_map,
        )
    )
    if first_parameter_class_fqn_list:
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=function_node.lineno,
                message=(
                    f"{callable_label} has first package-local object parameter class(es) "
                    f"{', '.join(first_parameter_class_fqn_list)}; move this behavior onto that object as an "
                    "instance method"
                ),
                path=relative_path,
            )
        )
    return finding_list


def _class_fqn_by_local_name_map_get(
    class_fqn_set: set[str],
    module_node: ast.Module,
    relative_path: str,
    relative_path_by_module_name_map: Mapping[str, str],
) -> dict[str, str]:
    """Return same-package class FQNs keyed by their local binding names.

    Args:
        class_fqn_set: All package-local class FQNs in the repository.
        module_node: Parsed current module.
        relative_path: Repository-relative current module path.
        relative_path_by_module_name_map: Repository paths keyed by module name.

    Returns:
        Same-package class bindings visible in the current module.
    """

    current_module_name = module_name_get(relative_path)
    package_root = _package_root_get(relative_path)
    class_fqn_by_local_name_map = {
        child_node.name: f"{current_module_name}.{child_node.name}"
        for child_node in module_node.body
        if isinstance(child_node, ast.ClassDef) and f"{current_module_name}.{child_node.name}" in class_fqn_set
    }
    for child_node in module_node.body:
        if not isinstance(child_node, ast.ImportFrom):
            continue
        imported_module_name = absolute_import_module_name_get(package_part_list_get(relative_path), child_node)
        if imported_module_name is None:
            continue
        imported_relative_path = relative_path_by_module_name_map.get(imported_module_name)
        if imported_relative_path is None or _package_root_get(imported_relative_path) != package_root:
            continue
        for alias_node in child_node.names:
            candidate_fqn = f"{imported_module_name}.{alias_node.name}"
            if candidate_fqn in class_fqn_set:
                class_fqn_by_local_name_map[alias_node.asname or alias_node.name] = candidate_fqn
    return class_fqn_by_local_name_map


def _class_fqn_set_get(relative_path_list: list[str], project_root: Path) -> set[str]:
    """Return top-level class FQNs declared under package-level owner roots.

    Args:
        relative_path_list: Complete non-Legacy root-owner Python scope.
        project_root: Exact repository root.

    Returns:
        Class FQNs declared below `lib/<package>` and `script/<package>`.
    """

    class_fqn_set: set[str] = set()
    for relative_path in relative_path_list:
        if _package_root_get(relative_path) is None:
            continue
        try:
            module_node = ast.parse(
                (project_root / relative_path).read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except OSError, SyntaxError:
            continue
        module_name = module_name_get(relative_path)
        class_fqn_set.update(
            f"{module_name}.{child_node.name}"
            for child_node in module_node.body
            if isinstance(child_node, ast.ClassDef)
        )
    return class_fqn_set


def _decorator_name_set_get(function_node: ast.stmt) -> set[str]:
    """Return visible decorator names for one callable.

    Args:
        function_node: Candidate function or method.

    Returns:
        Direct decorator tokens.
    """

    return {
        decorator_name
        for decorator_node in function_node.decorator_list
        if (decorator_name := call_name_get(decorator_node)) is not None
    }


def _direct_class_fqn_set_get(
    annotation_node: ast.expr | None,
    class_fqn_by_local_name_map: Mapping[str, str],
    class_fqn_set: set[str],
    module_name_by_local_name_map: Mapping[str, str],
) -> set[str]:
    """Return package-local classes used as the direct annotated value type.

    Args:
        annotation_node: Candidate annotation.
        class_fqn_by_local_name_map: Same-package class bindings.
        class_fqn_set: All package-local class FQNs.
        module_name_by_local_name_map: Same-package module bindings.

    Returns:
        Direct class FQNs, allowing only an optional union around the class.
    """

    annotation_node = _annotation_normalize(annotation_node)
    if annotation_node is None:
        return set()
    class_fqn = _node_class_fqn_get(
        annotation_node,
        class_fqn_by_local_name_map,
        class_fqn_set,
        module_name_by_local_name_map,
    )
    if class_fqn is not None:
        return {class_fqn}
    if isinstance(annotation_node, ast.BinOp) and isinstance(annotation_node.op, ast.BitOr):
        return _direct_class_fqn_set_get(
            annotation_node.left,
            class_fqn_by_local_name_map,
            class_fqn_set,
            module_name_by_local_name_map,
        ) | _direct_class_fqn_set_get(
            annotation_node.right,
            class_fqn_by_local_name_map,
            class_fqn_set,
            module_name_by_local_name_map,
        )
    return set()


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return package-local ownership findings for requested files.

    Args:
        request: Validated checker request.

    Returns:
        Findings from package-level `lib/**` and `script/**` owners.
    """

    project_root = Path(request["project_root"])
    all_relative_path_list = non_legacy_non_test_python_outside_submodule_relpath_list_get(
        project_root,
        scope="all",
    )
    eligible_relative_path_set = {
        relative_path for relative_path in all_relative_path_list if _package_root_get(relative_path) is not None
    }
    class_fqn_set = _class_fqn_set_get(all_relative_path_list, project_root)
    relative_path_by_module_name_map = relative_path_by_module_name_map_get(all_relative_path_list)
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if relative_path not in eligible_relative_path_set or not path.is_file():
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except SyntaxError:
            continue
        class_fqn_by_local_name_map = _class_fqn_by_local_name_map_get(
            class_fqn_set,
            module_node,
            relative_path,
            relative_path_by_module_name_map,
        )
        module_name_by_local_name_map = _module_name_by_local_name_map_get(
            module_node,
            relative_path,
            relative_path_by_module_name_map,
        )
        module_name = module_name_get(relative_path)
        for child_node in module_node.body:
            if isinstance(child_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                finding_list.extend(
                    _callable_finding_list_get(
                        f"top-level function {child_node.name}",
                        class_fqn_by_local_name_map,
                        class_fqn_set,
                        None,
                        child_node,
                        module_name_by_local_name_map,
                        relative_path,
                    )
                )
                continue
            if not isinstance(child_node, ast.ClassDef):
                continue
            current_class_fqn = f"{module_name}.{child_node.name}"
            for method_node in child_node.body:
                if not isinstance(method_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                    continue
                if _is_real_instance_method_match(method_node):
                    continue
                finding_list.extend(
                    _callable_finding_list_get(
                        f"non-instance method {child_node.name}.{method_node.name}",
                        class_fqn_by_local_name_map,
                        class_fqn_set,
                        current_class_fqn,
                        method_node,
                        module_name_by_local_name_map,
                        relative_path,
                    )
                )
    return finding_list


def _first_explicit_argument_get(
    function_node: ast.stmt,
) -> ast.arg | None:
    """Return the first non-classmethod-receiver argument.

    Args:
        function_node: Candidate function or non-instance method.

    Returns:
        First explicit argument after `cls`, when present.
    """

    argument_node_list = [
        *function_node.args.posonlyargs,
        *function_node.args.args,
        *function_node.args.kwonlyargs,
    ]
    if (
        "classmethod" in _decorator_name_set_get(function_node)
        and argument_node_list
        and argument_node_list[0].arg == "cls"
    ):
        argument_node_list = argument_node_list[1:]
    return argument_node_list[0] if argument_node_list else None


def _is_real_instance_method_match(function_node: ast.stmt) -> bool:
    """Return whether one class-body callable is a normal instance method.

    Args:
        function_node: Candidate method.

    Returns:
        Whether the first receiver is `self` and no non-instance decorator applies.
    """

    decorator_name_set = _decorator_name_set_get(function_node)
    return (
        "classmethod" not in decorator_name_set
        and "staticmethod" not in decorator_name_set
        and bool(function_node.args.args)
        and function_node.args.args[0].arg == "self"
    )


def _module_name_by_local_name_map_get(
    module_node: ast.Module,
    relative_path: str,
    relative_path_by_module_name_map: Mapping[str, str],
) -> dict[str, str]:
    """Return same-package module names keyed by local import bindings.

    Args:
        module_node: Parsed current module.
        relative_path: Repository-relative current module path.
        relative_path_by_module_name_map: Repository paths keyed by module name.

    Returns:
        Same-package imported module bindings.
    """

    package_root = _package_root_get(relative_path)
    module_name_by_local_name_map: dict[str, str] = {}
    for child_node in module_node.body:
        if isinstance(child_node, ast.Import):
            for alias_node in child_node.names:
                imported_relative_path = relative_path_by_module_name_map.get(alias_node.name)
                if imported_relative_path is not None and _package_root_get(imported_relative_path) == package_root:
                    module_name_by_local_name_map[alias_node.asname or alias_node.name.split(".", maxsplit=1)[0]] = (
                        alias_node.name
                    )
            continue
        if not isinstance(child_node, ast.ImportFrom):
            continue
        imported_module_name = absolute_import_module_name_get(package_part_list_get(relative_path), child_node)
        if imported_module_name is None:
            continue
        for alias_node in child_node.names:
            candidate_module_name = f"{imported_module_name}.{alias_node.name}"
            imported_relative_path = relative_path_by_module_name_map.get(candidate_module_name)
            if imported_relative_path is not None and _package_root_get(imported_relative_path) == package_root:
                module_name_by_local_name_map[alias_node.asname or alias_node.name] = candidate_module_name
    return module_name_by_local_name_map


def _nested_class_fqn_set_get(
    annotation_node: ast.expr | None,
    class_fqn_by_local_name_map: Mapping[str, str],
    class_fqn_set: set[str],
    module_name_by_local_name_map: Mapping[str, str],
) -> set[str]:
    """Return package-local classes referenced anywhere in one annotation.

    Args:
        annotation_node: Candidate annotation.
        class_fqn_by_local_name_map: Same-package class bindings.
        class_fqn_set: All package-local class FQNs.
        module_name_by_local_name_map: Same-package module bindings.

    Returns:
        Class FQNs used directly or as nested generic arguments.
    """

    annotation_node = _annotation_normalize(annotation_node)
    if annotation_node is None:
        return set()
    class_fqn = _node_class_fqn_get(
        annotation_node,
        class_fqn_by_local_name_map,
        class_fqn_set,
        module_name_by_local_name_map,
    )
    if class_fqn is not None:
        return {class_fqn}
    nested_class_fqn_set: set[str] = set()
    for child_node in ast.iter_child_nodes(annotation_node):
        if isinstance(child_node, ast.expr):
            nested_class_fqn_set.update(
                _nested_class_fqn_set_get(
                    child_node,
                    class_fqn_by_local_name_map,
                    class_fqn_set,
                    module_name_by_local_name_map,
                )
            )
    return nested_class_fqn_set


def _node_class_fqn_get(
    node: ast.expr,
    class_fqn_by_local_name_map: Mapping[str, str],
    class_fqn_set: set[str],
    module_name_by_local_name_map: Mapping[str, str],
) -> str | None:
    """Return a direct package-local class referenced by one expression.

    Args:
        node: Candidate annotation expression.
        class_fqn_by_local_name_map: Same-package class bindings.
        class_fqn_set: All package-local class FQNs.
        module_name_by_local_name_map: Same-package module bindings.

    Returns:
        Resolved class FQN or `None`.
    """

    if isinstance(node, ast.Name):
        return class_fqn_by_local_name_map.get(node.id)
    if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
        return None
    module_name = module_name_by_local_name_map.get(node.value.id)
    candidate_fqn = f"{module_name}.{node.attr}" if module_name is not None else ""
    return candidate_fqn if candidate_fqn in class_fqn_set else None


def _package_root_get(relative_path: str) -> str | None:
    """Return one `lib/<package>` or `script/<package>` owner root.

    Args:
        relative_path: Repository-relative Python path.

    Returns:
        Package root or `None` outside the package-level contract.
    """

    part_list = Path(relative_path).parts
    if len(part_list) < 3 or part_list[0] not in {"lib", "script"}:
        return None
    return "/".join(part_list[:2])


def _parameter_class_fqn_list_get(
    function_node: ast.stmt,
    class_fqn_by_local_name_map: dict[str, str],
    class_fqn_set: set[str],
    module_name_by_local_name_map: dict[str, str],
) -> list[str]:
    """Return direct package-local classes from all parameter annotations.

    Args:
        function_node: Candidate callable.
        class_fqn_by_local_name_map: Same-package class bindings.
        class_fqn_set: All package-local class FQNs.
        module_name_by_local_name_map: Same-package module bindings.

    Returns:
        Sorted unique parameter class FQNs.
    """

    argument_node_list = [
        *function_node.args.posonlyargs,
        *function_node.args.args,
        *function_node.args.kwonlyargs,
    ]
    if function_node.args.vararg is not None:
        argument_node_list.append(function_node.args.vararg)
    if function_node.args.kwarg is not None:
        argument_node_list.append(function_node.args.kwarg)
    parameter_class_fqn_set: set[str] = set()
    for argument_node in argument_node_list:
        parameter_class_fqn_set.update(
            _direct_class_fqn_set_get(
                argument_node.annotation,
                class_fqn_by_local_name_map,
                class_fqn_set,
                module_name_by_local_name_map,
            )
        )
    return sorted(parameter_class_fqn_set)


def main() -> int:
    """Run package-constructor checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
