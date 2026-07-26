#!/usr/bin/env python3
"""Check trivial top-level Python forwarding wrappers."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest


def _call_target_name_get(call_node: ast.Call) -> str | None:
    """Return a readable direct call target.

    Args:
        call_node: Candidate returned call.

    Returns:
        Direct function or one-level attribute target name.
    """

    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    if isinstance(call_node.func, ast.Attribute) and isinstance(call_node.func.value, ast.Name):
        return f"{call_node.func.value.id}.{call_node.func.attr}"
    return None


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return trivial top-level forwarding-wrapper findings.

    Args:
        request: Validated checker request.

    Returns:
        Findings across non-Legacy production Python.
    """

    project_root = Path(request["project_root"])
    eligible_relative_path_set = set(non_legacy_non_test_python_relpath_list_get(project_root, scope="all"))
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if relative_path not in eligible_relative_path_set or not path.is_file():
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except SyntaxError:
            continue
        for function_node in module_node.body:
            if not isinstance(function_node, ast.FunctionDef):
                continue
            call_node = _return_call_get(function_node)
            if call_node is None or not _is_forwarded_parameter_only_match(function_node, call_node):
                continue
            target_name = _call_target_name_get(call_node)
            if target_name is None:
                continue
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=function_node.lineno,
                    message=f"{function_node.name} is a trivial top-level proxy wrapper for {target_name}()",
                    path=relative_path,
                )
            )
    return finding_list


def _is_forwarded_parameter_only_match(function_node: ast.FunctionDef, call_node: ast.Call) -> bool:
    """Return whether one call uses only unchanged wrapper parameters.

    Args:
        function_node: Candidate wrapper function.
        call_node: Its directly returned call.

    Returns:
        Whether every call argument is a declared parameter reference.
    """

    parameter_name_set = {
        argument_node.arg
        for argument_node in (
            *function_node.args.posonlyargs,
            *function_node.args.args,
            *function_node.args.kwonlyargs,
        )
    }
    if function_node.args.vararg is not None:
        parameter_name_set.add(function_node.args.vararg.arg)
    if function_node.args.kwarg is not None:
        parameter_name_set.add(function_node.args.kwarg.arg)
    for argument_node in call_node.args:
        value_node = argument_node.value if isinstance(argument_node, ast.Starred) else argument_node
        if not isinstance(value_node, ast.Name) or value_node.id not in parameter_name_set:
            return False
    for keyword_node in call_node.keywords:
        if not isinstance(keyword_node.value, ast.Name) or keyword_node.value.id not in parameter_name_set:
            return False
    return True


def _return_call_get(function_node: ast.FunctionDef) -> ast.Call | None:
    """Return the one directly returned call from a trivial body.

    Args:
        function_node: Candidate top-level function.

    Returns:
        Call expression after an optional docstring and no other behavior.
    """

    statement_list = function_node.body[:]
    if (
        statement_list
        and isinstance(statement_list[0], ast.Expr)
        and isinstance(statement_list[0].value, ast.Constant)
        and isinstance(statement_list[0].value.value, str)
    ):
        statement_list = statement_list[1:]
    if (
        len(statement_list) == 1
        and isinstance(statement_list[0], ast.Return)
        and isinstance(statement_list[0].value, ast.Call)
    ):
        return statement_list[0].value
    return None


def main() -> int:
    """Run proxy-wrapper checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
