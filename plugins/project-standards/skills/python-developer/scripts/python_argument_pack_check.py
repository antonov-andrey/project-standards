#!/usr/bin/env python3

"""Check forbidden argument-pack helpers and pseudo-method helper callsites.

The checker enforces OOP transparency by detecting helper signatures that carry
injected dependency packs and method callsites that proxy object fields into helpers.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
import re
import sys
from typing import TypedDict

from lib.checker_runtime import main_project_scope_path_list_resolve, scope_args_add

ALLOW_RE = re.compile(r"#\s*argpack:\s*allow(?:\s+(?P<reason>.+))?", re.IGNORECASE)
DEPENDENCY_TOKEN_EXACT = {
    "session",
    "engine",
    "repo",
    "repository",
    "client",
    "page",
    "navigation",
    "delay_settings",
    "context",
    "logger",
    "config",
}
DEPENDENCY_TOKEN_PARTIAL = (
    "timeout",
    "retry",
    "session",
    "client",
    "repo",
    "config",
    "logger",
    "navigation",
    "delay",
)


def args_parse() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed CLI arguments.
    """

    parser = argparse.ArgumentParser(description="Check forbidden argument-pack helpers and pseudo-method callsites")
    scope_args_add(
        parser,
        scope_help="Optional explicit Main project Python files/directories. When provided, --scope is ignored.",
    )
    parser.add_argument(
        "--max-args",
        type=int,
        default=6,
        help="Maximum allowed helper arguments before argument-pack check triggers (default: 6).",
    )
    parser.add_argument(
        "--min-shared",
        type=int,
        default=3,
        help="Minimum shared dependency-like parameter names for repeated-pack warning (default: 3).",
    )
    parser.add_argument(
        "--fail-on-repeated-pack",
        action="store_true",
        help="Treat repeated dependency-pack findings as failures instead of warnings.",
    )
    return parser.parse_args()


def _argument_explosion_check_result_build(candidates: Iterable[FunctionInfo], max_args: int) -> FindingSplitResult:
    """Detect forbidden long signatures with dependency-like names.

    Args:
        candidates: Helper candidates.
        max_args: Maximum allowed arguments threshold.

    Returns:
        Split finding result.
    """

    fail_finding_list: list[Finding] = []
    warn_finding_list: list[Finding] = []

    for item in candidates:
        if item["comment_reason"] is not None:
            warn_finding_list.append(
                Finding(
                    level="WARN",
                    path=item["path"],
                    lineno=item["lineno"],
                    function_name=item["qualname"],
                    reason=(
                        "argpack allow-override is applied"
                        if item["comment_reason"] != "MISSING_REASON"
                        else "argpack allow-override is applied without reason"
                    ),
                )
            )
            continue

        if item["argument_count"] <= max_args:
            continue
        if not item["dependency_parameter_name_list"]:
            continue

        fail_finding_list.append(
            Finding(
                level="FAIL",
                path=item["path"],
                lineno=item["lineno"],
                function_name=item["qualname"],
                reason=(
                    f"argument explosion: args_count={item['argument_count']} > max_args={max_args} "
                    "with dependency-like parameters "
                    f"{sorted(item['dependency_parameter_name_list'])}"
                ),
            )
        )

    return FindingSplitResult(
        fail_finding_list=fail_finding_list,
        warn_finding_list=warn_finding_list,
    )


def _argument_field_count_by_object_name_map_compute(call: ast.Call) -> dict[str, int]:
    """Count object-field arguments by base name.

    Args:
        call: Call node.

    Returns:
        Mapping base name -> count of arguments sourced from `<base>.<field>`.
    """

    argument_field_count_by_object_name_map: dict[str, int] = {}

    argument_value_list: list[ast.AST] = list(call.args)
    argument_value_list.extend(keyword.value for keyword in call.keywords)

    for value in argument_value_list:
        if isinstance(value, ast.Starred):
            continue
        base = _attribute_base_name_get(value)
        if base is None:
            continue
        argument_field_count_by_object_name_map[base] = argument_field_count_by_object_name_map.get(base, 0) + 1
    return argument_field_count_by_object_name_map


def _attribute_base_name_get(node: ast.AST) -> str | None:
    """Return base object name for one-level attribute expression.

    Args:
        node: AST node.

    Returns:
        Base name for patterns like `self.field` or `ctx.field`.
    """

    if not isinstance(node, ast.Attribute):
        return None
    if not isinstance(node.value, ast.Name):
        return None
    return node.value.id


def _called_name_get(call: ast.Call) -> str | None:
    """Extract callable name for simple helper call patterns.

    Args:
        call: Call node.

    Returns:
        Bare callable name when resolvable.
    """

    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _comment_reason_get(source_line_list: Sequence[str], lineno: int) -> str | None:
    """Extract allow-comment reason from definition line.

    Args:
        source_line_list: Full source lines.
        lineno: 1-based definition line.

    Returns:
        Reason text or marker string when allow-comment exists.
    """

    if lineno < 1 or lineno > len(source_line_list):
        return None
    match = ALLOW_RE.search(source_line_list[lineno - 1])
    if match is None:
        return None
    reason = (match.group("reason") or "").strip()
    return reason or "MISSING_REASON"


def _finding_text_get(item: Finding) -> str:
    """Format finding line for review output.

    Args:
        item: Finding object.

    Returns:
        Formatted line.
    """

    return f"{item['level']}: {item['path']}:{item['lineno']} " f"{item['function_name']} -> {item['reason']}"


def _function_arg_list_collect(node: ast.AST) -> list[str]:
    """Collect function argument names excluding receiver names.

    Args:
        node: Function node.

    Returns:
        Ordered argument names.
    """

    argument_name_list: list[str] = []
    for arg in getattr(node.args, "posonlyargs", []):
        argument_name_list.append(arg.arg)
    for arg in node.args.args:
        argument_name_list.append(arg.arg)
    for arg in node.args.kwonlyargs:
        argument_name_list.append(arg.arg)
    return [name for name in argument_name_list if name not in {"self", "cls"}]


def _helper_name_set_by_module_name_map_build(
    candidates: Iterable[FunctionInfo],
) -> dict[str, set[str]]:
    """Build helper name index by module.

    Args:
        candidates: Function candidates.

    Returns:
        Mapping module name -> helper bare names.
    """

    helper_name_set_by_module_name_map: dict[str, set[str]] = {}
    for item in candidates:
        helper_name_set_by_module_name_map.setdefault(item["module_name"], set()).add(item["name"])
    return helper_name_set_by_module_name_map


def _is_classmethod(node: ast.AST) -> bool:
    """Return whether function node is decorated with `@classmethod`.

    Args:
        node: Function node.

    Returns:
        True when any decorator resolves to `classmethod`.
    """

    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "classmethod":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "classmethod":
            return True
    return False


def _is_dependency_like(name: str) -> bool:
    """Return whether parameter name looks dependency-like.

    Args:
        name: Parameter name.

    Returns:
        True for dependency-like names.
    """

    lowered = name.lower()
    if lowered in DEPENDENCY_TOKEN_EXACT:
        return True
    return any(token in lowered for token in DEPENDENCY_TOKEN_PARTIAL)


def _is_staticmethod(node: ast.AST) -> bool:
    """Return whether function node is decorated with `@staticmethod`.

    Args:
        node: Function node.

    Returns:
        True when any decorator resolves to `staticmethod`.
    """

    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "staticmethod":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "staticmethod":
            return True
    return False


def _module_candidate_scan_result_build(path: Path) -> ModuleCandidateScanResult:
    """Collect helper candidates and class methods for one module.

    Args:
        path: Python file path.

    Returns:
        Module candidate scan result.
    """

    source = path.read_text(encoding="utf-8")
    source_line_list = source.splitlines()
    tree = ast.parse(source, filename=str(path))

    module_name = path.as_posix()
    function_candidate_list: list[FunctionInfo] = []
    instance_method_list: list[InstanceMethodSpec] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            argument_name_list = _function_arg_list_collect(node)
            dependency_parameter_name_list = [
                argument_name for argument_name in argument_name_list if _is_dependency_like(argument_name)
            ]
            function_candidate_list.append(
                FunctionInfo(
                    path=path,
                    lineno=node.lineno,
                    qualname=node.name,
                    name=node.name,
                    module_name=module_name,
                    is_staticmethod=False,
                    dependency_parameter_name_list=dependency_parameter_name_list,
                    argument_count=len(argument_name_list),
                    node=node,
                    comment_reason=_comment_reason_get(source_line_list, node.lineno),
                )
            )
            continue

        if not isinstance(node, ast.ClassDef):
            continue

        for class_item in node.body:
            if not isinstance(class_item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            qualname = f"{node.name}.{class_item.name}"
            if _is_staticmethod(class_item):
                argument_name_list = _function_arg_list_collect(class_item)
                dependency_parameter_name_list = [
                    argument_name for argument_name in argument_name_list if _is_dependency_like(argument_name)
                ]
                function_candidate_list.append(
                    FunctionInfo(
                        path=path,
                        lineno=class_item.lineno,
                        qualname=qualname,
                        name=class_item.name,
                        module_name=module_name,
                        is_staticmethod=True,
                        dependency_parameter_name_list=dependency_parameter_name_list,
                        argument_count=len(argument_name_list),
                        node=class_item,
                        comment_reason=_comment_reason_get(source_line_list, class_item.lineno),
                    )
                )
            elif not _is_classmethod(class_item):
                instance_method_list.append(InstanceMethodSpec(qualname=qualname, node=class_item))

    return ModuleCandidateScanResult(
        function_candidate_list=function_candidate_list,
        instance_method_list=instance_method_list,
    )


def _pseudo_method_call_finding_list_build(
    *,
    candidates: Iterable[FunctionInfo],
    instance_method_list_by_module_name_map: Mapping[str, list[InstanceMethodSpec]],
) -> list[Finding]:
    """Detect helper callsites that forward object-field packs.

    Args:
        candidates: Helper candidates.
        instance_method_list_by_module_name_map: Instance methods keyed by module.

    Returns:
        Failure findings for pseudo-method helper calls.
    """

    helper_name_set_by_module_name_map = _helper_name_set_by_module_name_map_build(candidates)
    fail_finding_list: list[Finding] = []

    for module_name, instance_method_list in instance_method_list_by_module_name_map.items():
        helper_name_set = helper_name_set_by_module_name_map.get(module_name, set())
        if not helper_name_set:
            continue

        for method in instance_method_list:
            for call in [node for node in ast.walk(method["node"]) if isinstance(node, ast.Call)]:
                name = _called_name_get(call)
                if name is None or name not in helper_name_set:
                    continue

                argument_field_count_by_object_name_map = _argument_field_count_by_object_name_map_compute(call)
                violating_base = next(
                    (base for base, count in argument_field_count_by_object_name_map.items() if count >= 2),
                    None,
                )
                if violating_base is None:
                    continue

                fail_finding_list.append(
                    Finding(
                        level="FAIL",
                        path=Path(module_name),
                        lineno=call.lineno,
                        function_name=method["qualname"],
                        reason=(
                            "pseudo-method helper call: 2+ arguments sourced from "
                            f"{violating_base}.* into helper `{name}`; convert helper to method/collaborator"
                        ),
                    )
                )

    return fail_finding_list


def _repeated_pack_check_result_build(
    candidates: Iterable[FunctionInfo],
    *,
    min_shared: int,
    fail_on_repeated_pack: bool,
) -> FindingSplitResult:
    """Detect repeated dependency packs across functions in one module.

    Args:
        candidates: Helper candidates.
        min_shared: Minimum shared dependency names threshold.
        fail_on_repeated_pack: Promote findings to fail when True.

    Returns:
        Split finding result.
    """

    function_info_list_by_module_name_map: dict[str, list[FunctionInfo]] = {}
    for item in candidates:
        function_info_list_by_module_name_map.setdefault(item["module_name"], []).append(item)

    fail_finding_list: list[Finding] = []
    warn_finding_list: list[Finding] = []

    for function_info_list in function_info_list_by_module_name_map.values():
        for index, left in enumerate(function_info_list):
            if left["comment_reason"] is not None:
                continue
            if not left["dependency_parameter_name_list"]:
                continue
            for right in function_info_list[index + 1 :]:
                if right["comment_reason"] is not None:
                    continue
                if not right["dependency_parameter_name_list"]:
                    continue
                shared_dependency_parameter_name_list = sorted(
                    set(left["dependency_parameter_name_list"]) & set(right["dependency_parameter_name_list"])
                )
                if len(shared_dependency_parameter_name_list) < min_shared:
                    continue

                finding = Finding(
                    level="FAIL" if fail_on_repeated_pack else "WARN",
                    path=left["path"],
                    lineno=left["lineno"],
                    function_name=left["qualname"],
                    reason=(
                        "repeated dependency-pack across functions "
                        f"{left['qualname']} <-> {right['qualname']}; "
                        f"shared={shared_dependency_parameter_name_list}; "
                        "consider collaborator class or private owner method"
                    ),
                )
                if fail_on_repeated_pack:
                    fail_finding_list.append(finding)
                else:
                    warn_finding_list.append(finding)

    return FindingSplitResult(
        fail_finding_list=fail_finding_list,
        warn_finding_list=warn_finding_list,
    )


def _scope_path_list_build(args: argparse.Namespace) -> list[Path]:
    """Resolve analysis scope.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Sorted unique Python paths selected for analysis.
    """

    return sorted(dict.fromkeys(main_project_scope_path_list_resolve(args.paths, args.scope)))


def main() -> int:
    """Run argument-pack helper checker.

    Returns:
        Process exit code.
    """

    args = args_parse()
    if args.max_args < 1:
        print("--max-args must be >= 1")
        return 2
    if args.min_shared < 1:
        print("--min-shared must be >= 1")
        return 2

    try:
        scope = _scope_path_list_build(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not scope:
        print("INFO: argument-pack check skipped (no Python files in scope).")
        return 0

    function_info_list: list[FunctionInfo] = []
    instance_method_list_by_module_name_map: dict[str, list[InstanceMethodSpec]] = {}

    for path in scope:
        scan_result = _module_candidate_scan_result_build(path)
        function_info_list.extend(scan_result["function_candidate_list"])
        instance_method_list_by_module_name_map[path.as_posix()] = scan_result["instance_method_list"]

    fail_finding_list: list[Finding] = []
    warn_finding_list: list[Finding] = []

    argument_explosion_result = _argument_explosion_check_result_build(
        function_info_list,
        max_args=args.max_args,
    )
    fail_finding_list.extend(argument_explosion_result["fail_finding_list"])
    warn_finding_list.extend(argument_explosion_result["warn_finding_list"])

    repeated_pack_result = _repeated_pack_check_result_build(
        function_info_list,
        min_shared=args.min_shared,
        fail_on_repeated_pack=args.fail_on_repeated_pack,
    )
    fail_finding_list.extend(repeated_pack_result["fail_finding_list"])
    warn_finding_list.extend(repeated_pack_result["warn_finding_list"])

    fail_finding_list.extend(
        _pseudo_method_call_finding_list_build(
            candidates=function_info_list,
            instance_method_list_by_module_name_map=instance_method_list_by_module_name_map,
        )
    )

    if fail_finding_list:
        print("Python argument-pack violations:")
        for finding in sorted(
            fail_finding_list,
            key=lambda item: (item["path"].as_posix(), item["lineno"], item["function_name"]),
        ):
            print(_finding_text_get(finding))
        if warn_finding_list:
            print("\nPython argument-pack warnings:")
            for finding in sorted(
                warn_finding_list,
                key=lambda item: (item["path"].as_posix(), item["lineno"], item["function_name"]),
            ):
                print(_finding_text_get(finding))
        return 1

    if warn_finding_list:
        print("Python argument-pack warnings:")
        for finding in sorted(
            warn_finding_list,
            key=lambda item: (item["path"].as_posix(), item["lineno"], item["function_name"]),
        ):
            print(_finding_text_get(finding))
        print("Python argument-pack check passed with warnings.")
        return 0

    print("Python argument-pack check passed.")
    return 0


class Finding(TypedDict):
    """Represent one checker finding.

    Args:
        level: Severity level (`FAIL` or `WARN`).
        path: Source file path.
        lineno: Line number.
        function_name: Qualified function/method name.
        reason: Human-readable finding reason.
    """

    function_name: str
    level: str
    lineno: int
    path: Path
    reason: str


class FindingSplitResult(TypedDict):
    """Represent one split finding collection."""

    fail_finding_list: list[Finding]
    warn_finding_list: list[Finding]


class FunctionInfo(TypedDict):
    """Represent one helper candidate.

    Args:
        path: Source file path.
        lineno: Definition line number.
        qualname: Qualified function name (`fn`, `Class.fn`).
        name: Bare function name.
        module_name: File-local module identifier.
        is_staticmethod: Whether candidate is `@staticmethod`.
        dependency_parameter_name_list: Dependency-like parameter names.
        argument_count: Count of explicit named arguments excluding `self`/`cls`.
        node: AST node for the function definition.
        comment_reason: Allow-comment reason text when present.
    """

    argument_count: int
    comment_reason: str | None
    dependency_parameter_name_list: list[str]
    is_staticmethod: bool
    lineno: int
    module_name: str
    name: str
    node: ast.AST
    path: Path
    qualname: str


class InstanceMethodSpec(TypedDict):
    """Represent one instance method used for pseudo-method helper checks."""

    node: ast.AST
    qualname: str


class ModuleCandidateScanResult(TypedDict):
    """Represent one module-level candidate scan."""

    function_candidate_list: list[FunctionInfo]
    instance_method_list: list[InstanceMethodSpec]


if __name__ == "__main__":
    sys.exit(main())
