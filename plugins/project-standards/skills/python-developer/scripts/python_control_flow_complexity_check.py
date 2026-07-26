#!/usr/bin/env python3

"""Detect overloaded control flow in `Main project code` Python functions."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys
from typing import TypedDict

from lib.checker_runtime import main_project_scope_path_list_resolve, python_module_parse, scope_args_add

BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match, ast.IfExp)


def args_parse() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed argument namespace.
    """

    parser = argparse.ArgumentParser(description="Detect overloaded control flow in Main project Python functions.")
    scope_args_add(
        parser,
        scope_help="Optional explicit Main project Python files/directories. When provided, --scope is ignored.",
    )
    parser.add_argument(
        "--max-branches",
        type=int,
        default=10,
        help="Maximum allowed branch count before failure (default: 10).",
    )
    parser.add_argument(
        "--max-nesting",
        type=int,
        default=3,
        help="Maximum allowed branch nesting depth before failure (default: 3).",
    )
    return parser.parse_args()


def _control_flow_finding_list_build(path: Path, *, max_branches: int, max_nesting: int) -> list[Finding]:
    """Collect control-flow findings for one module.

    Args:
        path: Repository-relative Python file path.
        max_branches: Maximum allowed branch count.
        max_nesting: Maximum allowed nesting depth.

    Returns:
        Collected findings for the module.
    """

    finding_list: list[Finding] = []
    tree = python_module_parse(path)

    def visit_body(body_list: list[ast.stmt], prefix: str = "") -> None:
        """Visit one statement body recursively.

        Args:
            body_list: Statement list to inspect.
            prefix: Qualified-name prefix for nested class methods.
        """

        for node in body_list:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visitor = ControlFlowVisitor()
                for statement in node.body:
                    visitor.visit(statement)
                qualname = f"{prefix}{node.name}" if prefix else node.name
                if visitor._branch_count > max_branches or visitor._max_nesting > max_nesting:
                    finding_list.append(
                        Finding(
                            path=path,
                            lineno=node.lineno,
                            qualname=qualname,
                            branch_count=visitor._branch_count,
                            nesting_depth=visitor._max_nesting,
                        )
                    )
                continue
            if isinstance(node, ast.ClassDef):
                visit_body(node.body, prefix=f"{node.name}.")

    visit_body(tree.body)
    return finding_list


def main() -> int:
    """Run the checker CLI.

    Returns:
        Process exit code.
    """

    args = args_parse()
    scope = main_project_scope_path_list_resolve(args.paths, args.scope)
    finding_list: list[Finding] = []
    for path in scope:
        finding_list.extend(
            _control_flow_finding_list_build(path, max_branches=args.max_branches, max_nesting=args.max_nesting)
        )

    if not finding_list:
        print("Python control-flow complexity check passed.")
        return 0

    for finding in finding_list:
        print(
            f"{finding['path']}:{finding['lineno']}: {finding['qualname']}: "
            "control-flow complexity exceeds limits "
            f"(branches={finding['branch_count']}, nesting={finding['nesting_depth']})."
        )
    print("FAIL: Python control-flow complexity check failed.")
    return 1


class ControlFlowVisitor(ast.NodeVisitor):
    """Measure branch count and nesting depth for one function body."""

    def __init__(self) -> None:
        """Initialize zeroed control-flow counters."""

        self._branch_count = 0
        self._max_nesting = 0
        self._current_depth = 0

    def _branch_visit(self, node: ast.AST) -> None:
        """Visit one branching node and update counters.

        Args:
            node: Branch-like AST node.
        """

        self._branch_count += 1
        self._current_depth += 1
        self._max_nesting = max(self._max_nesting, self._current_depth)
        self.generic_visit(node)
        self._current_depth -= 1

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        """Handle one `if` branch node.

        Args:
            node: `if` AST node.
        """

        self._branch_visit(node)

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        """Handle one `for` branch node.

        Args:
            node: `for` AST node.
        """

        self._branch_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:  # noqa: N802
        """Handle one `async for` branch node.

        Args:
            node: `async for` AST node.
        """

        self._branch_visit(node)

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        """Handle one `while` branch node.

        Args:
            node: `while` AST node.
        """

        self._branch_visit(node)

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        """Handle one `try` branch node.

        Args:
            node: `try` AST node.
        """

        self._branch_count += max(1, len(node.handlers))
        self._current_depth += 1
        self._max_nesting = max(self._max_nesting, self._current_depth)
        self.generic_visit(node)
        self._current_depth -= 1

    def visit_Match(self, node: ast.Match) -> None:  # noqa: N802
        """Handle one `match` branch node.

        Args:
            node: `match` AST node.
        """

        self._branch_count += max(1, len(node.cases))
        self._current_depth += 1
        self._max_nesting = max(self._max_nesting, self._current_depth)
        self.generic_visit(node)
        self._current_depth -= 1

    def visit_IfExp(self, node: ast.IfExp) -> None:  # noqa: N802
        """Handle one ternary-expression branch node.

        Args:
            node: Ternary-expression AST node.
        """

        self._branch_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:  # noqa: N802
        """Count boolean short-circuit branches.

        Args:
            node: Boolean-operation AST node.
        """

        self._branch_count += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        """Skip nested function bodies inside the measured function.

        Args:
            node: Nested function AST node.
        """

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        """Skip nested async function bodies inside the measured function.

        Args:
            node: Nested async-function AST node.
        """

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        """Ignore nested lambdas for owner-level function complexity.

        Args:
            node: Lambda AST node.
        """


class Finding(TypedDict):
    """Represent one control-flow finding."""

    branch_count: int
    lineno: int
    nesting_depth: int
    path: Path
    qualname: str


if __name__ == "__main__":
    raise SystemExit(main())
