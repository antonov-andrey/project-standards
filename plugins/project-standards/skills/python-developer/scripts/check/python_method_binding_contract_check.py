#!/usr/bin/env python3
"""Check receiver, classmethod, staticmethod, and same-class dispatch rules."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import (
    non_legacy_non_test_python_outside_submodule_relpath_list_get,
    non_legacy_non_test_python_relpath_list_get,
)
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_syntax import call_name_get

FRAMEWORK_RECEIVERLESS_DECORATOR_NAME_SET = {
    "abstractmethod",
    "field_serializer",
    "field_validator",
    "model_serializer",
    "model_validator",
    "root_validator",
    "validator",
}


def _base_name_set_get(class_node: ast.ClassDef) -> set[str]:
    """Return direct base-class names for one class declaration.

    Args:
        class_node: Candidate class.

    Returns:
        Direct name or attribute tokens from its base list.
    """

    return {
        base_node.id if isinstance(base_node, ast.Name) else base_node.attr
        for base_node in class_node.bases
        if isinstance(base_node, (ast.Attribute, ast.Name))
    }


def _class_finding_list_get(
    class_node: ast.ClassDef,
    include_outside_submodule_only: bool,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return method-binding findings for one class.

    Args:
        class_node: Candidate class.
        include_outside_submodule_only: Whether root-owner-only rules apply.
        relative_path: Repository-relative source path.

    Returns:
        Method-binding findings for direct methods of the class.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    method_node_list = [
        child_node for child_node in class_node.body if isinstance(child_node, (ast.AsyncFunctionDef, ast.FunctionDef))
    ]
    method_name_set = {method_node.name for method_node in method_node_list}
    for method_node in method_node_list:
        decorator_name_set = _decorator_name_set_get(method_node)
        receiver_name = _receiver_name_get(method_node)
        display_name = f"{class_node.name}.{method_node.name}"
        if include_outside_submodule_only and _is_private_name_match(method_node.name):
            if "staticmethod" in decorator_name_set:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=method_node.lineno,
                        message=(
                            f"{display_name} uses forbidden private @staticmethod; move receiverless helper logic "
                            "to one private module-level function"
                        ),
                        path=relative_path,
                    )
                )
            if (
                "classmethod" in decorator_name_set
                and not decorator_name_set & FRAMEWORK_RECEIVERLESS_DECORATOR_NAME_SET
                and not _have_direct_cls_constructor(method_node)
            ):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=method_node.lineno,
                        message=(
                            f"{display_name} uses forbidden private @classmethod without direct return cls(...); "
                            "move helper logic to one private module-level function"
                        ),
                        path=relative_path,
                    )
                )
        if (
            include_outside_submodule_only
            and receiver_name == "self"
            and not _is_receiverless_exception_match(class_node, method_node)
            and not _is_receiver_used_match(method_node, "self")
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=method_node.lineno,
                    message=f"{display_name} is receiverless instance logic; move it to one module-level function",
                    path=relative_path,
                )
            )
        if (
            receiver_name == "cls"
            and not _is_classmethod_exact_shape_match(class_node, method_node)
            and not _is_receiver_used_match(method_node, "cls")
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=method_node.lineno,
                    message=f"{display_name} is receiverless @classmethod logic; move it to one module-level function",
                    path=relative_path,
                )
            )
        if (
            include_outside_submodule_only
            and "classmethod" in decorator_name_set
            and not _is_classmethod_exact_shape_match(class_node, method_node)
            and not method_node.name.startswith(("from_", "_from_"))
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=method_node.lineno,
                    message=(
                        f"{display_name} uses forbidden @classmethod outside one alternative constructor or "
                        "external exact-shape contract"
                    ),
                    path=relative_path,
                )
            )
        if not include_outside_submodule_only or ("staticmethod" not in decorator_name_set and receiver_name is None):
            continue
        for call_node in [node for node in ast.walk(method_node) if isinstance(node, ast.Call)]:
            if (
                not isinstance(call_node.func, ast.Attribute)
                or not isinstance(call_node.func.value, ast.Name)
                or call_node.func.value.id != class_node.name
                or call_node.func.attr not in method_name_set
            ):
                continue
            expected_receiver = "cls" if receiver_name == "cls" else "self"
            binding_name = (
                "@classmethod"
                if receiver_name == "cls"
                else "@staticmethod" if "staticmethod" in decorator_name_set else "instance method"
            )
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=call_node.lineno,
                    message=(
                        f"{display_name} is {binding_name} but calls same-class method via hardcoded "
                        f"{class_node.name}.{call_node.func.attr}() instead of "
                        f"{expected_receiver}.{call_node.func.attr}()"
                    ),
                    path=relative_path,
                )
            )
    return finding_list


def _decorator_name_set_get(function_node: ast.stmt) -> set[str]:
    """Return direct decorator names for one callable.

    Args:
        function_node: Candidate function or method.

    Returns:
        Resolved direct decorator tokens.
    """

    return {name for decorator_node in function_node.decorator_list if (name := call_name_get(decorator_node))}


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return method-binding findings across their exact source scopes.

    Args:
        request: Validated checker request.

    Returns:
        Root-owner and cross-submodule binding findings.
    """

    project_root = Path(request["project_root"])
    eligible_relative_path_set = set(non_legacy_non_test_python_relpath_list_get(project_root, scope="all"))
    outside_submodule_relative_path_set = set(
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
        include_outside_submodule_only = relative_path in outside_submodule_relative_path_set
        for class_node in [node for node in ast.walk(module_node) if isinstance(node, ast.ClassDef)]:
            finding_list.extend(_class_finding_list_get(class_node, include_outside_submodule_only, relative_path))
    return finding_list


def _have_direct_cls_constructor(function_node: ast.stmt) -> bool:
    """Return whether one method has a direct `return cls(...)` path.

    Args:
        function_node: Candidate classmethod.

    Returns:
        Whether any return directly constructs through `cls`.
    """

    return any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "cls"
        for node in ast.walk(function_node)
    )


def _is_classmethod_exact_shape_match(
    class_node: ast.ClassDef,
    function_node: ast.stmt,
) -> bool:
    """Return whether an external contract owns one classmethod shape.

    Args:
        class_node: Owning class.
        function_node: Candidate classmethod.

    Returns:
        Whether ORM or framework behavior fixes the method shape.
    """

    if function_node.name in {"__table_cls__", "orm_constructor_kwargs_validate"} and "OrmBase" in _base_name_set_get(
        class_node
    ):
        return True
    return _is_receiverless_exception_match(class_node, function_node)


def _is_private_name_match(name: str) -> bool:
    """Return whether a name is private but not dunder.

    Args:
        name: Candidate symbol name.

    Returns:
        Whether the name uses one leading underscore only.
    """

    return name.startswith("_") and not name.startswith("__")


def _is_receiver_used_match(
    function_node: ast.stmt,
    receiver_name: str,
) -> bool:
    """Return whether one method body uses its canonical receiver.

    Args:
        function_node: Candidate method.
        receiver_name: `self` or `cls`.

    Returns:
        Whether the receiver or instance `super()` dispatch is used.
    """

    for node in ast.walk(function_node):
        if isinstance(node, ast.Name) and node.id == receiver_name:
            return True
        if (
            receiver_name == "self"
            and isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "super"
        ):
            return True
    return False


def _is_receiverless_exception_match(
    class_node: ast.ClassDef,
    function_node: ast.stmt,
) -> bool:
    """Return whether one external contract permits receiverless method logic.

    Args:
        class_node: Owning class.
        function_node: Candidate method.

    Returns:
        Whether decorators, inheritance, IO, or visitor dispatch fix the shape.
    """

    if _decorator_name_set_get(function_node) & FRAMEWORK_RECEIVERLESS_DECORATOR_NAME_SET:
        return True
    base_name_set = _base_name_set_get(class_node)
    if base_name_set & {"BaseLoader", "Protocol"}:
        return True
    if "RawIOBase" in base_name_set and function_node.name in {"readable", "seekable"}:
        return True
    return function_node.name.startswith("visit_")


def _receiver_name_get(function_node: ast.stmt) -> str | None:
    """Return the canonical receiver declared by one method.

    Args:
        function_node: Candidate method.

    Returns:
        `self`, `cls`, or `None` for static or malformed receiverless shapes.
    """

    decorator_name_set = _decorator_name_set_get(function_node)
    if "staticmethod" in decorator_name_set:
        return None
    if "classmethod" in decorator_name_set:
        return "cls"
    if function_node.args.args and function_node.args.args[0].arg == "self":
        return "self"
    return None


def main() -> int:
    """Run method-binding checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
