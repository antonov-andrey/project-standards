#!/usr/bin/env python3
"""Check Product API route registration and standard-resource static boundaries."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_syntax import call_name_get, class_base_name_set_get

BACKEND_ROUTE_REGISTRATION_INTERNAL_RELATIVE_PATH = "backend/api_router.py"
DIRECT_FASTAPI_ROUTE_METHOD_NAME_SET = {
    "add_api_route",
    "api_route",
    "delete",
    "get",
    "head",
    "include_router",
    "options",
    "patch",
    "post",
    "put",
    "route",
    "trace",
    "websocket",
    "websocket_route",
}
FASTAPI_APP_RELATIVE_PATH = "backend/app.py"
HTTP_ROUTE_METHOD_NAME_SET = {"delete", "get", "patch", "post"}
STANDARD_RESOURCE_RUNTIME_METHOD_PATTERN = re.compile(
    r"^_[a-z0-9_]+_(?:collection_response_get|create|get|route_register|update)$"
)


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return route registration and standard-resource findings.

    Args:
        request: Validated checker process request.

    Returns:
        Static FastAPI bypass and duplicated resource-runtime findings.
    """

    project_root = Path(request["project_root"])
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if not relative_path.startswith("backend/") or not relative_path.endswith(".py") or not path.is_file():
            continue
        try:
            syntax_tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        except SyntaxError:
            continue
        finding_list.extend(_route_bypass_finding_list_get(syntax_tree, relative_path))
        finding_list.extend(_standard_resource_finding_list_get(syntax_tree, relative_path))
    return finding_list


def _have_trivial_response_mapping(function_node: ast.stmt) -> bool:
    """Return whether one response mapper only dumps a row into a model.

    Args:
        function_node: Candidate response mapper.

    Returns:
        Whether generated standard mapping replaces the entire function.
    """

    body_node_list = [
        node
        for node in function_node.body
        if not (
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        )
    ]
    if len(body_node_list) != 1 or not isinstance(body_node_list[0], ast.Return):
        return False
    return_node = body_node_list[0]
    if not isinstance(return_node.value, ast.Call):
        return False
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"model_dump", "payload_get"}
        for node in ast.walk(return_node.value)
    )


def _product_api_router_name_set_get(syntax_tree: ast.Module) -> set[str]:
    """Return simple names statically proven to hold ProductApiRouter objects.

    Args:
        syntax_tree: Parsed backend module.

    Returns:
        Module variables and annotated parameters that own ProductApiRouter.
    """

    product_api_router_type_name_set = {"ProductApiRouter"}
    for node in syntax_tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            if alias.name == "ProductApiRouter":
                product_api_router_type_name_set.add(alias.asname or alias.name)
    router_name_set: set[str] = set()
    for node in ast.walk(syntax_tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and call_name_get(node.value) in product_api_router_type_name_set
        ):
            router_name_set.add(node.targets[0].id)
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for argument_node in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            if (
                argument_node.annotation is not None
                and call_name_get(argument_node.annotation) in product_api_router_type_name_set
            ):
                router_name_set.add(argument_node.arg)
    return router_name_set


def _route_bypass_finding_list_get(
    syntax_tree: ast.Module,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return direct FastAPI registration bypass findings.

    Args:
        syntax_tree: Parsed backend module.
        relative_path: Repository-relative backend path.

    Returns:
        APIRouter, FastAPI, app route, and direct registration findings.
    """

    if relative_path == BACKEND_ROUTE_REGISTRATION_INTERNAL_RELATIVE_PATH:
        return []
    apirouter_name_set = {"APIRouter"}
    fastapi_name_set = {"FastAPI"}
    for node in ast.walk(syntax_tree):
        if not isinstance(node, ast.ImportFrom) or node.module != "fastapi":
            continue
        for alias in node.names:
            if alias.name == "APIRouter":
                apirouter_name_set.add(alias.asname or alias.name)
            elif alias.name == "FastAPI":
                fastapi_name_set.add(alias.asname or alias.name)
    product_api_router_name_set = _product_api_router_name_set_get(syntax_tree)
    finding_list: list[ProjectStandardCheckerFinding] = []
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.ImportFrom) and node.module == "fastapi":
            for alias in node.names:
                if alias.name == "APIRouter":
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=node.lineno,
                            message=(
                                "direct APIRouter import is forbidden outside "
                                f"{BACKEND_ROUTE_REGISTRATION_INTERNAL_RELATIVE_PATH}"
                            ),
                            path=relative_path,
                        )
                    )
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            for decorator_node in node.decorator_list:
                if (
                    not isinstance(decorator_node, ast.Call)
                    or not isinstance(decorator_node.func, ast.Attribute)
                    or decorator_node.func.attr not in DIRECT_FASTAPI_ROUTE_METHOD_NAME_SET
                    or (
                        isinstance(decorator_node.func.value, ast.Name)
                        and decorator_node.func.value.id in {"app", *product_api_router_name_set}
                    )
                ):
                    continue
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=node.lineno,
                        message=f"direct @{decorator_node.func.attr} route decorator is forbidden",
                        path=relative_path,
                    )
                )
        if not isinstance(node, ast.Call):
            continue
        call_name = call_name_get(node)
        if call_name in apirouter_name_set:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=(
                        "direct APIRouter() construction is forbidden outside "
                        f"{BACKEND_ROUTE_REGISTRATION_INTERNAL_RELATIVE_PATH}"
                    ),
                    path=relative_path,
                )
            )
        if call_name in fastapi_name_set and relative_path != FASTAPI_APP_RELATIVE_PATH:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=f"direct FastAPI() construction is allowed only in {FASTAPI_APP_RELATIVE_PATH}",
                    path=relative_path,
                )
            )
        if not isinstance(node.func, ast.Attribute):
            continue
        if (
            isinstance(node.func.value, ast.Name)
            and node.func.value.id == "app"
            and node.func.attr in DIRECT_FASTAPI_ROUTE_METHOD_NAME_SET
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=f"direct app.{node.func.attr} route registration is forbidden",
                    path=relative_path,
                )
            )
        if node.func.attr in {"add_api_route", "api_route", "include_router"}:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message=f"direct {node.func.attr} route registration is forbidden",
                    path=relative_path,
                )
            )
    return finding_list


def _standard_resource_finding_list_get(
    syntax_tree: ast.Module,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return manual standard-resource route and runtime findings.

    Args:
        syntax_tree: Parsed backend module.
        relative_path: Repository-relative backend path.

    Returns:
        Manual decorators, duplicate runtime, and trivial mapper findings.
    """

    resource_class_node_list = [
        node
        for node in syntax_tree.body
        if isinstance(node, ast.ClassDef) and "ProductApiResource" in class_base_name_set_get(node)
    ]
    if not resource_class_node_list:
        return []
    function_node_by_name_map = {
        node.name: node for node in syntax_tree.body if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
    }
    finding_list: list[ProjectStandardCheckerFinding] = []
    for class_node in resource_class_node_list:
        for method_node in class_node.body:
            if not isinstance(method_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            if method_node.name not in {
                "_row_create",
                "_row_update",
            } and STANDARD_RESOURCE_RUNTIME_METHOD_PATTERN.fullmatch(method_node.name):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=method_node.lineno,
                        message=f"{method_node.name} duplicates standard ProductApiResource runtime",
                        path=relative_path,
                    )
                )
            for decorator_node in method_node.decorator_list:
                if isinstance(decorator_node, ast.Call) and call_name_get(decorator_node) in HTTP_ROUTE_METHOD_NAME_SET:
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=method_node.lineno,
                            message=(
                                f"{method_node.name} uses one manual @{call_name_get(decorator_node)} "
                                "standard-resource route decorator"
                            ),
                            path=relative_path,
                        )
                    )
        init_node = next(
            (
                node
                for node in class_node.body
                if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "__init__"
            ),
            None,
        )
        if init_node is None:
            continue
        for node in ast.walk(init_node):
            if not isinstance(node, ast.keyword) or node.arg != "response_get" or not isinstance(node.value, ast.Name):
                continue
            response_function_node = function_node_by_name_map.get(node.value.id)
            if response_function_node is not None and _have_trivial_response_mapping(response_function_node):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=node.lineno,
                        message=f"{node.value.id} duplicates generated standard response mapping",
                        path=relative_path,
                    )
                )
    return finding_list


def main() -> int:
    """Run the Product API route registration checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
