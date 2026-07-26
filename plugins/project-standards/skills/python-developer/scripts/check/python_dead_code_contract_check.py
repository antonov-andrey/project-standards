#!/usr/bin/env python3
"""Check dead and test-only root-owner Python definitions."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import shlex
import sys
import tomllib

import vulture

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.git_repository import submodule_name_by_path_map_get
from project_standards.project_scope import (
    non_legacy_non_test_python_outside_submodule_relpath_list_get,
    python_relpath_list_get,
)
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_import import relative_path_by_module_name_map_get
from project_standards.python_symbol import (
    local_load_line_set_by_name_map_get,
    python_symbol_definition_by_fqn_map_get,
    python_symbol_use_path_set_by_fqn_map_get,
)
from project_standards.python_syntax import call_name_get

IMPLICIT_USE_DECORATOR_NAME_SET = {
    "checks",
    "computed_field",
    "field_serializer",
    "field_validator",
    "model_serializer",
    "model_validator",
    "root_validator",
    "validator",
}


def _decorator_name_set_get(function_node: ast.stmt) -> set[str]:
    """Return visible decorator names for one callable.

    Args:
        function_node: Candidate callable.

    Returns:
        Direct decorator tokens.
    """

    return {
        decorator_name
        for decorator_node in function_node.decorator_list
        if (decorator_name := call_name_get(decorator_node)) is not None
    }


def _embedded_call_name_set_get(project_root: Path, relative_path_list: list[str]) -> set[str]:
    """Return callable names explicitly embedded in production source strings.

    Args:
        project_root: Exact repository root.
        relative_path_list: Production Python scan scope.

    Returns:
        Names followed by `(` inside one literal runtime-source string.
    """

    embedded_call_name_set: set[str] = set()
    for relative_path in relative_path_list:
        try:
            module_node = ast.parse(
                (project_root / relative_path).read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except OSError, SyntaxError:
            continue
        for node in ast.walk(module_node):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or "(" not in node.value:
                continue
            embedded_call_name_set.update(re.findall(r"\b([A-Za-z_]\w*)\s*\(", node.value))
    return embedded_call_name_set


def _external_callable_name_set_by_path_map_get(
    project_root: Path,
    relative_path_list: list[str],
) -> dict[str, set[str]]:
    """Return callable names referenced by packaging and pytest configuration.

    Args:
        project_root: Exact repository root.
        relative_path_list: Production Python scan scope.

    Returns:
        External callable names keyed by defining repository path.
    """

    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.is_file():
        return {}
    try:
        payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except OSError, tomllib.TOMLDecodeError:
        return {}
    relative_path_by_module_name_map = relative_path_by_module_name_map_get(relative_path_list)
    external_callable_name_set_by_path_map: dict[str, set[str]] = {}
    project_payload = payload.get("project")
    if isinstance(project_payload, dict):
        script_payload = project_payload.get("scripts")
        if isinstance(script_payload, dict):
            for target in script_payload.values():
                if not isinstance(target, str) or ":" not in target:
                    continue
                module_name, callable_name = target.split(":", maxsplit=1)
                relative_path = relative_path_by_module_name_map.get(module_name)
                if relative_path is not None:
                    external_callable_name_set_by_path_map.setdefault(relative_path, set()).add(callable_name)
    plugin_module_name_set: set[str] = set()
    tool_payload = payload.get("tool")
    if isinstance(tool_payload, dict):
        pytest_payload = tool_payload.get("pytest")
        if isinstance(pytest_payload, dict):
            ini_payload = pytest_payload.get("ini_options")
            if isinstance(ini_payload, dict):
                raw_addopts = ini_payload.get("addopts")
                if isinstance(raw_addopts, str):
                    option_list = shlex.split(raw_addopts)
                elif isinstance(raw_addopts, list) and all(isinstance(item, str) for item in raw_addopts):
                    option_list = list(raw_addopts)
                else:
                    option_list = []
                for index, option in enumerate(option_list[:-1]):
                    if option == "-p":
                        plugin_module_name_set.add(option_list[index + 1])
    for plugin_module_name in plugin_module_name_set:
        relative_path = relative_path_by_module_name_map.get(plugin_module_name)
        if relative_path is None:
            continue
        try:
            module_node = ast.parse(
                (project_root / relative_path).read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except OSError, SyntaxError:
            continue
        external_callable_name_set_by_path_map.setdefault(relative_path, set()).update(
            child_node.name
            for child_node in module_node.body
            if isinstance(child_node, (ast.AsyncFunctionDef, ast.FunctionDef)) and child_node.name.startswith("pytest_")
        )
    return external_callable_name_set_by_path_map


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return dead and test-only definition findings.

    Args:
        request: Validated checker request.

    Returns:
        Top-level symbol and base-less method findings.
    """

    project_root = Path(request["project_root"])
    submodule_relative_path_list = list(submodule_name_by_path_map_get(project_root))
    full_use_relative_path_list = [
        relative_path
        for relative_path in python_relpath_list_get(project_root, scope="all")
        if not _is_under_submodule_match(relative_path, submodule_relative_path_list)
    ]
    production_use_relative_path_list = [
        relative_path
        for relative_path in full_use_relative_path_list
        if "test" not in Path(relative_path).parts and relative_path != "conftest.py"
    ]
    definition_relative_path_list = non_legacy_non_test_python_outside_submodule_relpath_list_get(
        project_root,
        scope="all",
    )
    definition_by_fqn_map = python_symbol_definition_by_fqn_map_get(
        project_root,
        definition_relative_path_list,
    )
    production_use_path_set_by_fqn_map = python_symbol_use_path_set_by_fqn_map_get(
        project_root,
        production_use_relative_path_list,
    )
    full_use_path_set_by_fqn_map = python_symbol_use_path_set_by_fqn_map_get(
        project_root,
        full_use_relative_path_list,
    )
    embedded_call_name_set = _embedded_call_name_set_get(project_root, production_use_relative_path_list)
    external_callable_name_set_by_path_map = _external_callable_name_set_by_path_map_get(
        project_root,
        production_use_relative_path_list,
    )
    requested_path_set = set(request["path_list"])
    module_node_by_path_map: dict[str, ast.Module] = {}
    finding_list: list[ProjectStandardCheckerFinding] = []
    for symbol_fqn, definition in sorted(definition_by_fqn_map.items()):
        relative_path = definition["path"]
        if relative_path not in requested_path_set:
            continue
        if definition["kind"] == "class" and _is_private_name_match(definition["name"]):
            continue
        if relative_path not in module_node_by_path_map:
            try:
                module_node_by_path_map[relative_path] = ast.parse(
                    (project_root / relative_path).read_text(encoding="utf-8"),
                    filename=relative_path,
                )
            except OSError, SyntaxError:
                continue
        module_node = module_node_by_path_map[relative_path]
        definition_node = next(
            (
                child_node
                for child_node in module_node.body
                if isinstance(child_node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef))
                and child_node.name == definition["name"]
                and child_node.lineno == definition["line"]
            ),
            None,
        )
        if (
            isinstance(definition_node, (ast.AsyncFunctionDef, ast.FunctionDef))
            and _decorator_name_set_get(definition_node) & IMPLICIT_USE_DECORATOR_NAME_SET
        ):
            continue
        if definition["name"] in embedded_call_name_set:
            continue
        if definition["name"] in external_callable_name_set_by_path_map.get(relative_path, set()):
            continue
        if _is_direct_execution_script_match(project_root / relative_path) and definition["name"] in {
            "args_parse",
            "main",
        }:
            continue
        production_external_use_path_set = production_use_path_set_by_fqn_map.get(symbol_fqn, set()) - {relative_path}
        if production_external_use_path_set:
            continue
        full_external_use_path_set = full_use_path_set_by_fqn_map.get(symbol_fqn, set()) - {relative_path}
        local_use_line_set = {
            line
            for line in local_load_line_set_by_name_map_get(module_node).get(definition["name"], set())
            if line != definition["line"]
        }
        if local_use_line_set:
            continue
        classification = "used only in tests" if full_external_use_path_set else "dead"
        use_text = f": {', '.join(sorted(full_external_use_path_set))}" if full_external_use_path_set else ""
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=definition["line"],
                message=f"{classification} {definition['kind']} {definition['name']}{use_text}",
                path=relative_path,
            )
        )

    method_definition_by_key_map = _method_definition_by_key_map_get(
        project_root,
        definition_relative_path_list,
    )
    production_unused_method_key_set = _unused_method_key_set_get(
        project_root,
        production_use_relative_path_list,
        method_definition_by_key_map,
    )
    full_unused_method_key_set = _unused_method_key_set_get(
        project_root,
        full_use_relative_path_list,
        method_definition_by_key_map,
    )
    for key in sorted(full_unused_method_key_set | production_unused_method_key_set):
        relative_path, line_text, method_name = key.split("\0")
        if relative_path not in requested_path_set:
            continue
        if key in full_unused_method_key_set:
            classification = "dead"
        else:
            classification = "used only in tests"
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=int(line_text),
                message=f"{classification} method {method_definition_by_key_map[key]}",
                path=relative_path,
            )
        )
    return finding_list


def _is_direct_execution_script_match(path: Path) -> bool:
    """Return whether one module contains a top-level main guard.

    Args:
        path: Candidate Python source.

    Returns:
        Whether a canonical `__main__` comparison exists at module scope.
    """

    try:
        module_node = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    except OSError, SyntaxError:
        return False
    return any(
        isinstance(child_node, ast.If)
        and isinstance(child_node.test, ast.Compare)
        and any(isinstance(node, ast.Name) and node.id == "__name__" for node in ast.walk(child_node.test))
        and any(isinstance(node, ast.Constant) and node.value == "__main__" for node in ast.walk(child_node.test))
        for child_node in module_node.body
    )


def _is_private_name_match(name: str) -> bool:
    """Return whether one name is private but not dunder.

    Args:
        name: Candidate name.

    Returns:
        Whether the name uses one leading underscore.
    """

    return name.startswith("_") and not name.startswith("__")


def _is_under_submodule_match(relative_path: str, submodule_relative_path_list: list[str]) -> bool:
    """Return whether one path belongs to a direct submodule.

    Args:
        relative_path: Repository-relative path.
        submodule_relative_path_list: Direct submodule roots.

    Returns:
        Whether the path is at or below one submodule root.
    """

    return any(
        relative_path == submodule_relative_path or relative_path.startswith(f"{submodule_relative_path}/")
        for submodule_relative_path in submodule_relative_path_list
    )


def _method_definition_by_key_map_get(
    project_root: Path,
    definition_relative_path_list: list[str],
) -> dict[str, str]:
    """Return eligible base-less class methods keyed by stable source identity.

    Args:
        project_root: Exact repository root.
        definition_relative_path_list: Root-owner definition paths.

    Returns:
        Display names keyed by `path`, line, and method identity.
    """

    method_definition_by_key_map: dict[str, str] = {}
    for relative_path in definition_relative_path_list:
        try:
            module_node = ast.parse(
                (project_root / relative_path).read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except OSError, SyntaxError:
            continue
        for class_node in module_node.body:
            if not isinstance(class_node, ast.ClassDef) or class_node.bases:
                continue
            for method_node in class_node.body:
                if not isinstance(method_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                    continue
                if _decorator_name_set_get(method_node) & IMPLICIT_USE_DECORATOR_NAME_SET:
                    continue
                key = f"{relative_path}\0{method_node.lineno}\0{method_node.name}"
                method_definition_by_key_map[key] = f"{class_node.name}.{method_node.name}"
    return method_definition_by_key_map


def _unused_method_key_set_get(
    project_root: Path,
    relative_path_list: list[str],
    method_definition_by_key_map: dict[str, str],
) -> set[str]:
    """Return eligible methods reported unused by Vulture.

    Args:
        project_root: Exact repository root.
        relative_path_list: Python scan scope.
        method_definition_by_key_map: Eligible methods keyed by source identity.

    Returns:
        Unused method keys.
    """

    scanner = vulture.Vulture(verbose=False)
    scanner.scavenge([str(project_root / relative_path) for relative_path in relative_path_list])
    unused_method_key_set: set[str] = set()
    for item in scanner.get_unused_code():
        if item.typ != "method":
            continue
        try:
            relative_path = Path(item.filename).resolve().relative_to(project_root).as_posix()
        except ValueError:
            continue
        key = f"{relative_path}\0{item.first_lineno}\0{item.name}"
        if key in method_definition_by_key_map:
            unused_method_key_set.add(key)
    return unused_method_key_set


def main() -> int:
    """Run dead-code checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
