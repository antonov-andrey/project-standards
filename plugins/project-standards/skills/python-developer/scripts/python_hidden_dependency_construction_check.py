#!/usr/bin/env python3

"""Detect hidden dependency construction and service-locator use in `Main project code`."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import sys

from lib.checker_runtime import main_project_scope_path_list_resolve, python_module_parse, scope_args_add

ALLOWED_FACTORY_NAMES = {"main", "__init__", "build", "create", "bootstrap", "configure"}
ALLOWED_FACTORY_PREFIXES = ("build_", "create_", "make_", "bootstrap_", "configure_")
DEPENDENCY_CONSTRUCTOR_EXACT = {"create_engine", "sessionmaker"}
DEPENDENCY_CONSTRUCTOR_SUFFIXES = ("Client", "Repository", "Repo", "Session", "Engine", "Cache", "Transport")
SERVICE_LOCATOR_ATTRS = {"resolve", "get", "require"}
SERVICE_LOCATOR_BASE_TOKENS = {"container", "locator", "registry", "services", "service_locator"}


def args_parse() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed argument namespace.
    """

    parser = argparse.ArgumentParser(
        description="Detect hidden dependency construction and service-locator use in Main project Python code."
    )
    scope_args_add(
        parser,
        scope_help="Optional explicit Main project Python files/directories. When provided, --scope is ignored.",
    )
    return parser.parse_args()


def _dotted_name_get(node: ast.AST) -> str | None:
    """Render one attribute/name chain into dotted text.

    Args:
        node: Candidate AST node.

    Returns:
        Dotted name when representable, else `None`.
    """

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name_get(node.value)
        if prefix is None:
            return None
        return f"{prefix}.{node.attr}"
    return None


def _finding_list_build(path: Path) -> list[Finding]:
    """Collect hidden-dependency findings for one module.

    Args:
        path: Repository-relative Python file path.

    Returns:
        Collected findings for the module.
    """

    findings: list[Finding] = []
    tree = python_module_parse(path)

    def function_inspect(
        node: ast.AST,
        *,
        qualname: str,
    ) -> None:
        """Inspect one function or method for hidden dependency patterns.

        Args:
            node: Function or method AST node.
            qualname: Qualified owner name for reporting.
        """

        if _is_allowed_factory(node.name):
            return
        for call in (candidate for candidate in ast.walk(node) if isinstance(candidate, ast.Call)):
            if _is_service_locator_call(call):
                findings.append(
                    Finding(
                        path=path,
                        lineno=call.lineno,
                        qualname=qualname,
                        reason="service-locator resolution inside runtime flow is forbidden",
                    )
                )
                return
            if _is_dependency_constructor_call(call):
                findings.append(
                    Finding(
                        path=path,
                        lineno=call.lineno,
                        qualname=qualname,
                        reason="hidden dependency construction inside runtime flow is forbidden",
                    )
                )
                return

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_inspect(node, qualname=node.name)
            continue
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function_inspect(child, qualname=f"{node.name}.{child.name}")
    return findings


def _is_allowed_factory(name: str) -> bool:
    """Return whether one owner name is an allowed explicit factory/composition root.

    Args:
        name: Owner name to classify.

    Returns:
        True when the owner is an allowed explicit factory/composition root.
    """

    return name in ALLOWED_FACTORY_NAMES or any(name.startswith(prefix) for prefix in ALLOWED_FACTORY_PREFIXES)


def _is_dependency_constructor_call(call: ast.Call) -> bool:
    """Return whether one call target looks like dependency construction.

    Args:
        call: Candidate call node.

    Returns:
        True when the call target looks like dependency construction.
    """

    target = _target_name_call_get(call)
    if target is None:
        return False
    final_name = target.rsplit(".", 1)[-1]
    if final_name in DEPENDENCY_CONSTRUCTOR_EXACT:
        return True
    return any(final_name.endswith(suffix) for suffix in DEPENDENCY_CONSTRUCTOR_SUFFIXES)


def _is_service_locator_call(call: ast.Call) -> bool:
    """Return whether one call matches a service-locator pattern.

    Args:
        call: Candidate call node.

    Returns:
        True when the call matches one service-locator pattern.
    """

    if not isinstance(call.func, ast.Attribute) or call.func.attr not in SERVICE_LOCATOR_ATTRS:
        return False
    base = _dotted_name_get(call.func.value)
    if base is None:
        return False
    return any(token in base.split(".") for token in SERVICE_LOCATOR_BASE_TOKENS)


def _target_name_call_get(call: ast.Call) -> str | None:
    """Return dotted call target name when representable.

    Args:
        call: Candidate call node.

    Returns:
        Dotted call target name when representable, else `None`.
    """

    return _dotted_name_get(call.func)


def main() -> int:
    """Run the checker CLI.

    Returns:
        Process exit code.
    """

    args = args_parse()
    scope = main_project_scope_path_list_resolve(args.paths, args.scope)
    findings: list[Finding] = []
    for path in scope:
        findings.extend(_finding_list_build(path))

    if not findings:
        print("Python hidden-dependency construction check passed.")
        return 0

    for finding in findings:
        print(f"{finding.path}:{finding.lineno}: {finding.qualname}: {finding.reason}.")
    print("FAIL: Python hidden-dependency construction check failed.")
    return 1


@dataclass(frozen=True)
class Finding:
    """Represent one hidden-dependency finding."""

    lineno: int
    path: Path
    qualname: str
    reason: str


if __name__ == "__main__":
    raise SystemExit(main())
