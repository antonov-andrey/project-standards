#!/usr/bin/env python3
"""Check singular core tokens in Python function and method names."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

EXTERNAL_API_PATH_RE = re.compile(r"^/v\d+/")
EXTERNAL_CALLABLE_NAME_BY_PATH_SUFFIX_MAP = {
    "config_argparse/parser.py": {
        "_format_actions_usage",
        "_get_actions_usage_parts",
        "_split_lines",
        "add_arguments",
    },
    "ozon_seller_api/client.py": {
        "product_info_attributes",
        "product_info_prices",
    },
}
SINGULAR_S_TOKEN_SET = {
    "access",
    "alias",
    "allows",
    "analysis",
    "analytics",
    "args",
    "aws",
    "axis",
    "bypass",
    "bytes",
    "class",
    "cls",
    "compress",
    "contents",
    "docs",
    "exists",
    "https",
    "ingress",
    "is",
    "kms",
    "kwargs",
    "kubernetes",
    "ms",
    "os",
    "pass",
    "postgres",
    "process",
    "progress",
    "props",
    "readiness",
    "receiverless",
    "requests",
    "rss",
    "sales",
    "seconds",
    "settings",
    "stats",
    "status",
    "subclass",
    "suppress",
}
TOO_MANY_REQUESTS_RE = re.compile(r"\btoo many requests\b", re.IGNORECASE)


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return plural-token findings in non-Legacy production Python.

    Args:
        request: Validated checker request.

    Returns:
        Findings across the root repository and direct submodules.
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
        for node in ast.walk(module_node):
            if (
                not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
                or node.name.startswith("__")
                and node.name.endswith("__")
                or _is_external_callable_name_match(node, relative_path)
            ):
                continue
            plural_token_list = _plural_token_list_get(node, relative_path)
            if plural_token_list:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=node.lineno,
                        message=f"{node.name} uses forbidden plural tokens {plural_token_list}",
                        path=relative_path,
                    )
                )
    return finding_list


def _is_external_callable_name_match(
    function_node: ast.stmt,
    relative_path: str,
) -> bool:
    """Return whether an external framework owns one exact callable name.

    Args:
        function_node: Candidate function or method.
        relative_path: Repository-relative module path.

    Returns:
        Whether one inherited or framework API fixes the name.
    """

    if any(
        relative_path.endswith(path_suffix) and function_node.name in callable_name_set
        for path_suffix, callable_name_set in EXTERNAL_CALLABLE_NAME_BY_PATH_SUFFIX_MAP.items()
    ):
        return True
    if function_node.name.startswith("_") or "ozon_seller_api/" not in relative_path:
        return False
    return any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and EXTERNAL_API_PATH_RE.match(node.value.strip())
        for node in ast.walk(function_node)
    )


def _is_helm_values_boundary_match(function_node: ast.stmt) -> bool:
    """Return whether `values` denotes an actual Helm values artifact.

    Args:
        function_node: Candidate function or method.

    Returns:
        Whether body or documentation evidence identifies the Helm boundary.
    """

    for node in ast.walk(function_node):
        if isinstance(node, ast.Name) and "HELM" in node.id and "VALUES" in node.id:
            return True
        if isinstance(node, ast.Attribute) and "HELM" in node.attr and "VALUES" in node.attr:
            return True
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        text = node.value.lower()
        if "helm values" in text or "-values.sha256" in text:
            return True
    return False


def _is_requests_token_allowed(
    function_node: ast.stmt,
    relative_path: str,
) -> bool:
    """Return whether `requests` belongs to a real external boundary.

    Args:
        function_node: Candidate function or method.
        relative_path: Repository-relative module path.

    Returns:
        Whether retry or protocol evidence owns the plural token.
    """

    if relative_path.startswith("retry_runtime/"):
        return True
    return any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and TOO_MANY_REQUESTS_RE.search(node.value)
        for node in ast.walk(function_node)
    )


def _plural_token_list_get(
    function_node: ast.stmt,
    relative_path: str,
) -> list[str]:
    """Return forbidden plural-looking tokens in one callable name.

    Args:
        function_node: Candidate function or method.
        relative_path: Repository-relative module path.

    Returns:
        Stable forbidden token list.
    """

    plural_token_list: list[str] = []
    for token in function_node.name.lstrip("_").split("_"):
        if not token.endswith("s") or token in SINGULAR_S_TOKEN_SET:
            continue
        if token == "requests" and _is_requests_token_allowed(function_node, relative_path):
            continue
        if token == "lines" and "json_lines" in function_node.name:
            continue
        if token == "principals" and "iam_allowed_principals" in function_node.name:
            continue
        if token == "values" and _is_helm_values_boundary_match(function_node):
            continue
        plural_token_list.append(token)
    return plural_token_list


def main() -> int:
    """Run plural-token checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
