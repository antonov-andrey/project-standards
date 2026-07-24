"""Shared AST helpers for proxy/call_wrap anti-pattern checks."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

TOP_LEVEL_ALLOWLIST = {
    "main",
}


def delegate_call_get(stmt: ast.stmt) -> ast.Call | None:
    """Extract delegated call from one-statement function body.

    Args:
        stmt: Single executable statement.

    Returns:
        Call node for direct `call(...)` or `return call(...)`, else `None`.
    """

    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return stmt.value
    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call):
        return stmt.value
    return None


def executable_statement_list_collect(node: ast.AST) -> list[ast.stmt]:
    """Return executable function body without leading docstring node.

    Args:
        node: Function or method AST node.

    Returns:
        Executable statements.
    """

    body = list(node.body)
    if body and isinstance(body[0], ast.Expr):
        value = getattr(body[0], "value", None)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return body[1:]
    return body


def _is_literal_like(node: ast.AST) -> bool:
    """Return whether node is a static literal expression.

    Args:
        node: Candidate AST node.

    Returns:
        True when node is literal-like.
    """

    if isinstance(node, ast.Constant):
        return True
    try:
        ast.literal_eval(node)
    except Exception:
        return False
    return True


def forwarding_call_analysis_build(call: ast.Call, *, param_list: list[str]) -> ForwardingCallAnalysis:
    """Validate call uses only forwarded parameters and literals.

    Args:
        call: Delegated call node.
        param_list: Function parameter names excluding receivers.

    Returns:
        Forwarded-call analysis result.
    """

    used_params: set[str] = set()
    has_literal = False

    for arg in call.args:
        if isinstance(arg, ast.Starred):
            value = arg.value
            if not isinstance(value, ast.Name) or value.id not in param_list or value.id in used_params:
                return ForwardingCallAnalysis(is_valid=False, has_literal=False)
            used_params.add(value.id)
            continue
        if isinstance(arg, ast.Name) and arg.id in param_list and arg.id not in used_params:
            used_params.add(arg.id)
            continue
        if _is_literal_like(arg):
            has_literal = True
            continue
        return ForwardingCallAnalysis(is_valid=False, has_literal=False)

    for keyword in call.keywords:
        value = keyword.value
        if keyword.arg is None:
            if not isinstance(value, ast.Name) or value.id not in param_list or value.id in used_params:
                return ForwardingCallAnalysis(is_valid=False, has_literal=False)
            used_params.add(value.id)
            continue
        if isinstance(value, ast.Name) and value.id in param_list:
            if value.id in used_params:
                return ForwardingCallAnalysis(is_valid=False, has_literal=False)
            used_params.add(value.id)
            continue
        if _is_literal_like(value):
            has_literal = True
            continue
        return ForwardingCallAnalysis(is_valid=False, has_literal=False)

    return ForwardingCallAnalysis(is_valid=True, has_literal=has_literal)


def is_parameter_forwarding_pure(call: ast.Call, *, param_list: list[str]) -> bool:
    """Validate delegated call forwards function parameters only.

    Args:
        call: Delegated call node.
        param_list: Function parameter names excluding receivers.

    Returns:
        True when forwarding is pure pass-through without transformations.
    """

    if not param_list:
        return len(call.args) == 0 and len(call.keywords) == 0

    forwarded: set[str] = set()
    for arg in call.args:
        if isinstance(arg, ast.Starred):
            value = arg.value
            if not isinstance(value, ast.Name) or value.id not in param_list or value.id in forwarded:
                return False
            forwarded.add(value.id)
            continue
        if not isinstance(arg, ast.Name) or arg.id not in param_list or arg.id in forwarded:
            return False
        forwarded.add(arg.id)

    for keyword in call.keywords:
        if keyword.arg is None:
            value = keyword.value
            if not isinstance(value, ast.Name) or value.id not in param_list or value.id in forwarded:
                return False
            forwarded.add(value.id)
            continue
        if keyword.arg not in param_list:
            return False
        if not isinstance(keyword.value, ast.Name) or keyword.value.id != keyword.arg or keyword.arg in forwarded:
            return False
        forwarded.add(keyword.arg)

    return forwarded == set(param_list)


def is_probable_constructor_target(call: ast.Call) -> bool:
    """Return whether call target looks like a constructor.

    Args:
        call: Candidate call node.

    Returns:
        True when target name looks constructor-like.
    """

    func = call.func
    if isinstance(func, ast.Name):
        return bool(func.id) and func.id[0].isupper()
    if isinstance(func, ast.Attribute):
        return bool(func.attr) and func.attr[0].isupper()
    return False


def parameter_name_list_collect(node: ast.AST) -> list[str]:
    """Collect parameter names excluding receivers.

    Args:
        node: Function or method AST node.

    Returns:
        Ordered parameter names.
    """

    names: list[str] = []
    for arg in getattr(node.args, "posonlyargs", []):
        names.append(arg.arg)
    for arg in node.args.args:
        names.append(arg.arg)
    if node.args.vararg is not None:
        names.append(node.args.vararg.arg)
    for arg in node.args.kwonlyargs:
        names.append(arg.arg)
    if node.args.kwarg is not None:
        names.append(node.args.kwarg.arg)
    return [name for name in names if name not in {"self", "cls"}]


def _is_super_init_call(call: ast.Call) -> bool:
    """Check whether call target is `super().__init__(...)`.

    Args:
        call: Candidate call node.

    Returns:
        True when call target is `super().__init__`.
    """

    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr != "__init__":
        return False
    value = func.value
    return isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "super"


def _meaningful_method_list_build(class_node: ast.ClassDef) -> list[ast.AST]:
    """Collect class methods excluding pure docstrings and nested classes.

    Args:
        class_node: Class AST node.

    Returns:
        Declared methods.
    """

    return [item for item in class_node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]


def thin_subclass_violation_get(path: Path, node: ast.ClassDef) -> Finding | None:
    """Detect subclasses that only prefill constants in `__init__`.

    Args:
        path: Source file path.
        node: Class AST node.

    Returns:
        Finding when class is a forbidden thin subclass, else `None`.
    """

    if not node.bases:
        return None
    methods = _meaningful_method_list_build(node)
    if len(methods) != 1 or methods[0].name != "__init__":
        return None

    init_method = methods[0]
    body = executable_statement_list_collect(init_method)
    if len(body) != 1:
        return None
    call = delegate_call_get(body[0])
    if call is None or not _is_super_init_call(call):
        return None

    forwarding_analysis = forwarding_call_analysis_build(call, param_list=parameter_name_list_collect(init_method))
    if not forwarding_analysis.is_valid or not forwarding_analysis.has_literal:
        return None
    return Finding(
        path=path,
        lineno=node.lineno,
        symbol=f"class {node.name}",
        reason="thin subclass that only fixes constants in __init__ is forbidden",
    )


@dataclass(frozen=True)
class Finding:
    """Represent one checker finding."""

    lineno: int
    path: Path
    reason: str
    symbol: str


@dataclass(frozen=True)
class ForwardingCallAnalysis:
    """Represent one forwarded-call analysis result."""

    has_literal: bool
    is_valid: bool
