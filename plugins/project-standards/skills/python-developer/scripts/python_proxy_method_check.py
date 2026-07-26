#!/usr/bin/env python3

"""Check and forbid pass-through proxy symbols in Python product code.

Detects:
- class methods that only delegate to another callable,
- top-level free functions that only call one method or constructor,
- thin subclasses whose only behavior is fixing constants in `__init__`,
- helper modules that contain only pass-through symbols.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys
from typing import TypedDict

from lib.checker_runtime import main_project_scope_path_list_resolve, scope_args_add
from lib.python_proxy_analysis import (
    Finding,
    TOP_LEVEL_ALLOWLIST,
    delegate_call_get,
    executable_statement_list_collect,
    forwarding_call_analysis_build,
    is_parameter_forwarding_pure,
    is_probable_constructor_target,
    parameter_name_list_collect,
    thin_subclass_violation_get,
)


def args_parse() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed argument namespace.
    """

    parser = argparse.ArgumentParser(description="Check and forbid pass-through proxy symbols in Python code.")
    scope_args_add(
        parser,
        scope_help="Optional explicit Main project Python files/directories. When provided, --scope is ignored.",
    )
    return parser.parse_args()


def _free_function_violation_get(
    path: Path,
    node: ast.AST,
) -> Finding | None:
    """Detect top-level free-function pass-through proxies.

    Args:
        path: Source file path.
        node: Top-level function node.

    Returns:
        Finding when function is a forbidden proxy, else `None`.
    """

    if node.name in TOP_LEVEL_ALLOWLIST:
        return None
    body = executable_statement_list_collect(node)
    if len(body) != 1:
        return None
    call = delegate_call_get(body[0])
    if call is None or _is_self_or_super_delegate(call):
        return None

    param_list = parameter_name_list_collect(node)
    if is_parameter_forwarding_pure(call, param_list=param_list):
        target = ast.unparse(call.func) if hasattr(ast, "unparse") else "<delegate>"
        return Finding(
            path=path,
            lineno=node.lineno,
            symbol=f"function {node.name}",
            reason=f"pure pass-through free function to {target} is forbidden",
        )
    if _is_pure_free_function_method_proxy(call, param_list=param_list):
        target = ast.unparse(call.func) if hasattr(ast, "unparse") else "<delegate>"
        return Finding(
            path=path,
            lineno=node.lineno,
            symbol=f"function {node.name}",
            reason=f"pure pass-through free function to {target} is forbidden",
        )

    forwarding_analysis = forwarding_call_analysis_build(call, param_list=param_list)
    if forwarding_analysis["is_valid"] and forwarding_analysis["has_literal"] and is_probable_constructor_target(call):
        target = ast.unparse(call.func) if hasattr(ast, "unparse") else "<constructor>"
        return Finding(
            path=path,
            lineno=node.lineno,
            symbol=f"function {node.name}",
            reason=f"thin constructor/profile call_wrap to {target} is forbidden",
        )
    return None


def _is_pure_free_function_method_proxy(call: ast.Call, *, param_list: list[str]) -> bool:
    """Validate free-function proxy to one forwarded method receiver.

    Args:
        call: Delegated call node.
        param_list: Function parameter names.

    Returns:
        True when call shape is `receiver.method(other_forwarded_params...)`.
    """

    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    if not isinstance(func.value, ast.Name) or func.value.id not in param_list:
        return False

    forwarded_parameter_name_set: set[str] = {func.value.id}
    for arg in call.args:
        if isinstance(arg, ast.Starred):
            value = arg.value
            if (
                not isinstance(value, ast.Name)
                or value.id not in param_list
                or value.id in forwarded_parameter_name_set
            ):
                return False
            forwarded_parameter_name_set.add(value.id)
            continue
        if not isinstance(arg, ast.Name) or arg.id not in param_list or arg.id in forwarded_parameter_name_set:
            return False
        forwarded_parameter_name_set.add(arg.id)

    for keyword in call.keywords:
        if keyword.arg is None:
            value = keyword.value
            if (
                not isinstance(value, ast.Name)
                or value.id not in param_list
                or value.id in forwarded_parameter_name_set
            ):
                return False
            forwarded_parameter_name_set.add(value.id)
            continue
        if (
            not isinstance(keyword.value, ast.Name)
            or keyword.value.id not in param_list
            or keyword.value.id in forwarded_parameter_name_set
        ):
            return False
        forwarded_parameter_name_set.add(keyword.value.id)

    return forwarded_parameter_name_set == set(param_list)


def _is_self_or_super_delegate(call: ast.Call) -> bool:
    """Check delegated target is `self.method(...)` or `super().method(...)`.

    Args:
        call: Candidate call node.

    Returns:
        True when call target is instance or `super()` delegation.
    """

    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    value = func.value
    if isinstance(value, ast.Name) and value.id == "self":
        return True
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "super":
        return True
    return False


def _method_proxy_violation_list_build(path: Path, node: ast.ClassDef) -> list[Finding]:
    """Collect pass-through method findings inside one class.

    Args:
        path: Source file path.
        node: Class AST node.

    Returns:
        Method-level findings.
    """

    finding_list: list[Finding] = []
    for method in node.body:
        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = executable_statement_list_collect(method)
        if len(body) != 1:
            continue
        call = delegate_call_get(body[0])
        if call is None or not _is_self_or_super_delegate(call):
            continue
        param_list = parameter_name_list_collect(method)
        if not is_parameter_forwarding_pure(call, param_list=param_list):
            continue
        target = ast.unparse(call.func) if hasattr(ast, "unparse") else "<delegate>"
        finding_list.append(
            Finding(
                path=path,
                lineno=method.lineno,
                symbol=f"class {node.name} def {method.name}",
                reason=f"pure pass-through proxy to {target} is forbidden",
            )
        )
    return finding_list


def _proxy_violation_list_build(path: Path) -> list[str]:
    """Collect proxy-symbol violations in one Python file.

    Args:
        path: Python file path to inspect.

    Returns:
        Violation messages with file and location details.
    """

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    finding_list: list[Finding] = []
    top_level_symbol_def_list = _top_level_symbol_def_list_compute(tree)
    top_level_violation_symbol_identity_set: set[str] = set()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            finding = _free_function_violation_get(path, node)
            if finding is not None:
                finding_list.append(finding)
                top_level_violation_symbol_identity_set.add(f"function\0{node.name}")
            continue

        if not isinstance(node, ast.ClassDef):
            continue

        finding = thin_subclass_violation_get(path, node)
        if finding is not None:
            finding_list.append(finding)
            top_level_violation_symbol_identity_set.add(f"class\0{node.name}")

        finding_list.extend(_method_proxy_violation_list_build(path, node))

    top_level_symbol_identity_set = {f"{symbol['kind']}\0{symbol['name']}" for symbol in top_level_symbol_def_list}
    if top_level_symbol_identity_set and top_level_symbol_identity_set == top_level_violation_symbol_identity_set:
        module_line = min(symbol["lineno"] for symbol in top_level_symbol_def_list)
        finding_list.append(
            Finding(
                path=path,
                lineno=module_line,
                symbol="module",
                reason="helper module contains only pass-through symbols",
            )
        )

    return [f"{item['path']}:{item['lineno']} {item['symbol']}: {item['reason']}" for item in finding_list]


def _top_level_symbol_def_list_compute(tree: ast.Module) -> list[TopLevelSymbolDef]:
    """Collect top-level function and class symbols.

    Args:
        tree: Parsed module tree.

    Returns:
        Top-level symbol rows.
    """

    symbol_list: list[TopLevelSymbolDef] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbol_list.append(TopLevelSymbolDef(kind="function", name=node.name, lineno=node.lineno))
        elif isinstance(node, ast.ClassDef):
            symbol_list.append(TopLevelSymbolDef(kind="class", name=node.name, lineno=node.lineno))
    return symbol_list


def main() -> int:
    """Run proxy-symbol ban check.

    Returns:
        Process exit code.
    """

    args = args_parse()
    try:
        scope = main_project_scope_path_list_resolve(args.paths, args.scope)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not scope:
        print("INFO: proxy-method check skipped (no Python files in scope).")
        return 0

    violation_list: list[str] = []
    for path in scope:
        violation_list.extend(_proxy_violation_list_build(path))

    if violation_list:
        print("Python proxy-method violations:")
        for violation in violation_list:
            print(violation)
        return 1

    print("Python proxy-method check passed.")
    return 0


class TopLevelSymbolDef(TypedDict):
    """Represent one top-level function or class definition."""

    kind: str
    lineno: int
    name: str


if __name__ == "__main__":
    sys.exit(main())
