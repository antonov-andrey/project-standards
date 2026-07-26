#!/usr/bin/env python3
"""Check that callable business-data carriers do not use tuples."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_outside_submodule_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest


def _annotation_node_get(annotation_node: ast.expr | None) -> ast.expr | None:
    """Return a parsed annotation node, including quoted annotations.

    Args:
        annotation_node: Raw annotation expression.

    Returns:
        Normalized annotation expression when available.
    """

    if not isinstance(annotation_node, ast.Constant) or not isinstance(annotation_node.value, str):
        return annotation_node
    try:
        return ast.parse(annotation_node.value, mode="eval").body
    except SyntaxError:
        return None


def _body_node_list_get(statement_list: list[ast.stmt]) -> list[ast.AST]:
    """Return body-owned nodes without entering nested callable scopes.

    Args:
        statement_list: Callable body statements.

    Returns:
        Lexically ordered nodes owned by the callable.
    """

    node_list: list[ast.AST] = []
    stack_list: list[ast.AST] = list(reversed(statement_list))
    while stack_list:
        node = stack_list.pop()
        node_list.append(node)
        if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Lambda)):
            continue
        stack_list.extend(reversed(list(ast.iter_child_nodes(node))))
    return node_list


def _callable_finding_list_get(
    callable_name: str,
    function_node: ast.stmt,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return tuple-carrier findings owned by one callable.

    Args:
        callable_name: Lexically qualified callable name.
        function_node: Callable declaration.
        relative_path: Repository-relative source path.

    Returns:
        Tuple annotation, return, and local-storage findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    constant_name_set: set[str] = set()
    for parameter_node in _parameter_node_list_get(function_node):
        for annotation_text in _tuple_annotation_text_list_get(parameter_node.annotation):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=function_node.lineno,
                    message=(
                        f"{callable_name} uses forbidden tuple carrier annotation for parameter "
                        f"{parameter_node.arg}: {annotation_text}"
                    ),
                    path=relative_path,
                )
            )
    for annotation_text in _tuple_annotation_text_list_get(function_node.returns):
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=function_node.lineno,
                message=f"{callable_name} uses forbidden tuple carrier annotation in return: {annotation_text}",
                path=relative_path,
            )
        )
    for node in _body_node_list_get(function_node.body):
        if isinstance(node, ast.AnnAssign):
            target_name = _target_name_get(node.target)
            if target_name is not None:
                for annotation_text in _tuple_annotation_text_list_get(node.annotation):
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=node.lineno,
                            message=(
                                f"{callable_name} uses forbidden tuple carrier annotation for local "
                                f"{target_name}: {annotation_text}"
                            ),
                            path=relative_path,
                        )
                    )
        if isinstance(node, ast.Return):
            tuple_value_text = _tuple_value_text_get(node.value)
            if tuple_value_text is not None:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=node.lineno,
                        message=f"{callable_name} returns forbidden tuple carrier expression: {tuple_value_text}",
                        path=relative_path,
                    )
                )
            continue
        if isinstance(node, ast.Assign):
            tuple_value_text = _tuple_value_text_get(node.value)
            if tuple_value_text is None:
                continue
            target_name_list = [
                target_name
                for target_node in node.targets
                if (target_name := _target_name_get(target_node)) is not None
            ]
            if _is_constant_tuple_match(node.value, constant_name_set):
                constant_name_set.update(target_name_list)
                continue
            for target_name in target_name_list:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=node.lineno,
                        message=f"{callable_name} stores forbidden tuple carrier in {target_name}: {tuple_value_text}",
                        path=relative_path,
                    )
                )
            continue
        if not isinstance(node, ast.AnnAssign):
            continue
        tuple_value_text = _tuple_value_text_get(node.value)
        target_name = _target_name_get(node.target)
        if tuple_value_text is None or target_name is None:
            continue
        if _is_constant_tuple_match(node.value, constant_name_set):
            constant_name_set.add(target_name)
            continue
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=node.lineno,
                message=f"{callable_name} stores forbidden tuple carrier in {target_name}: {tuple_value_text}",
                path=relative_path,
            )
        )
    return finding_list


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return tuple-carrier findings in the root-repository definition scope.

    Args:
        request: Validated checker request.

    Returns:
        Deterministic findings outside Legacy, tests, and direct submodules.
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
        finding_list.extend(_statement_finding_list_get("", relative_path, module_node.body))
    return finding_list


def _is_constant_data_match(value_node: ast.expr | None, constant_name_set: set[str]) -> bool:
    """Return whether one expression consists only of immutable constant data.

    Args:
        value_node: Candidate expression.
        constant_name_set: Local names already known to hold constant tuples.

    Returns:
        Whether the expression is static constant data.
    """

    try:
        ast.literal_eval(value_node)
    except SyntaxError, TypeError, ValueError:
        pass
    else:
        return True
    if isinstance(value_node, ast.Name):
        return value_node.id in constant_name_set
    if isinstance(value_node, ast.Starred):
        return _is_constant_data_match(value_node.value, constant_name_set)
    if isinstance(value_node, ast.Tuple):
        return all(_is_constant_data_match(item, constant_name_set) for item in value_node.elts)
    return False


def _is_constant_tuple_match(value_node: ast.expr | None, constant_name_set: set[str]) -> bool:
    """Return whether one value is an immutable tuple constant.

    Args:
        value_node: Candidate expression.
        constant_name_set: Local names already known to hold constant tuples.

    Returns:
        Whether the value is one hardcoded tuple expression.
    """

    return isinstance(value_node, ast.Tuple) and all(
        _is_constant_data_match(item, constant_name_set) for item in value_node.elts
    )


def _parameter_node_list_get(function_node: ast.stmt) -> list[ast.arg]:
    """Return every declared parameter node in declaration order.

    Args:
        function_node: Callable declaration.

    Returns:
        Positional, keyword-only, variadic, and keyword parameter nodes.
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
    return argument_node_list


def _statement_finding_list_get(
    owner_prefix: str,
    relative_path: str,
    statement_list: list[ast.stmt],
) -> list[ProjectStandardCheckerFinding]:
    """Return tuple-carrier findings through nested lexical owners.

    Args:
        owner_prefix: Current class or callable prefix.
        relative_path: Repository-relative source path.
        statement_list: Statements in the current lexical owner.

    Returns:
        Findings from all callables below the owner.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    for statement_node in statement_list:
        if isinstance(statement_node, ast.ClassDef):
            finding_list.extend(
                _statement_finding_list_get(
                    f"{owner_prefix}{statement_node.name}.",
                    relative_path,
                    statement_node.body,
                )
            )
            continue
        if not isinstance(statement_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        callable_name = f"{owner_prefix}{statement_node.name}"
        finding_list.extend(_callable_finding_list_get(callable_name, statement_node, relative_path))
        finding_list.extend(
            _statement_finding_list_get(
                f"{callable_name}.",
                relative_path,
                statement_node.body,
            )
        )
    return finding_list


def _target_name_get(target_node: ast.expr) -> str | None:
    """Return one assignment carrier target without destructuring targets.

    Args:
        target_node: Assignment target expression.

    Returns:
        Rendered target name, or `None` for destructuring.
    """

    return None if isinstance(target_node, (ast.List, ast.Tuple)) else ast.unparse(target_node)


def _tuple_annotation_text_list_get(annotation_node: ast.expr | None) -> list[str]:
    """Return tuple annotations found anywhere inside one annotation.

    Args:
        annotation_node: Candidate annotation expression.

    Returns:
        Tuple annotation texts in lexical order.
    """

    normalized_node = _annotation_node_get(annotation_node)
    if normalized_node is None:
        return []
    if (
        isinstance(normalized_node, ast.Subscript)
        and isinstance(normalized_node.value, ast.Name)
        and normalized_node.value.id in {"Tuple", "tuple"}
    ):
        return [ast.unparse(normalized_node)]
    tuple_annotation_text_list: list[str] = []
    for child_node in ast.iter_child_nodes(normalized_node):
        if isinstance(child_node, ast.expr):
            tuple_annotation_text_list.extend(_tuple_annotation_text_list_get(child_node))
    return tuple_annotation_text_list


def _tuple_value_text_get(value_node: ast.expr | None) -> str | None:
    """Return rendered text for one runtime tuple carrier expression.

    Args:
        value_node: Candidate runtime expression.

    Returns:
        Tuple expression text when matched.
    """

    if isinstance(value_node, ast.Tuple):
        return ast.unparse(value_node)
    if isinstance(value_node, ast.Call) and isinstance(value_node.func, ast.Name) and value_node.func.id == "tuple":
        return ast.unparse(value_node)
    return None


def main() -> int:
    """Run the tuple-carrier contract checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
