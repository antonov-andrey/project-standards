#!/usr/bin/env python3

"""Check forbidden argument-pack helpers and pseudo-method helper callsites.

The checker enforces OOP transparency by detecting helper signatures that carry
injected dependency packs and method callsites that proxy object fields into helpers.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Iterable

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


def _arg_object_field_count_map_compute(call: ast.Call) -> dict[str, int]:
    """Count object-field arguments by base name.

    Args:
        call: Call node.

    Returns:
        Mapping base name -> count of arguments sourced from `<base>.<field>`.
    """

    counts: dict[str, int] = {}

    values: list[ast.AST] = list(call.args)
    values.extend(keyword.value for keyword in call.keywords)

    for value in values:
        if isinstance(value, ast.Starred):
            continue
        base = _attribute_base_name_get(value)
        if base is None:
            continue
        counts[base] = counts.get(base, 0) + 1
    return counts


def _argument_explosion_check_result_build(candidates: Iterable[FunctionInfo], max_args: int) -> FindingSplitResult:
    """Detect forbidden long signatures with dependency-like names.

    Args:
        candidates: Helper candidates.
        max_args: Maximum allowed arguments threshold.

    Returns:
        Split finding result.
    """

    fails: list[Finding] = []
    warns: list[Finding] = []

    for item in candidates:
        if item.comment_reason is not None:
            warns.append(
                Finding(
                    level="WARN",
                    path=item.path,
                    lineno=item.lineno,
                    function_name=item.qualname,
                    reason=(
                        "argpack allow-override is applied"
                        if item.comment_reason != "MISSING_REASON"
                        else "argpack allow-override is applied without reason"
                    ),
                )
            )
            continue

        if item.args_count <= max_args:
            continue
        if not item.dependency_param_list:
            continue

        fails.append(
            Finding(
                level="FAIL",
                path=item.path,
                lineno=item.lineno,
                function_name=item.qualname,
                reason=(
                    f"argument explosion: args_count={item.args_count} > max_args={max_args} "
                    f"with dependency-like parameters {sorted(item.dependency_param_list)}"
                ),
            )
        )

    return FindingSplitResult(fail_finding_list=fails, warn_finding_list=warns)


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

    return f"{item.level}: {item.path}:{item.lineno} {item.function_name} -> {item.reason}"


def _function_arg_list_collect(node: ast.AST) -> list[str]:
    """Collect function argument names excluding receiver names.

    Args:
        node: Function node.

    Returns:
        Ordered argument names.
    """

    names: list[str] = []
    for arg in getattr(node.args, "posonlyargs", []):
        names.append(arg.arg)
    for arg in node.args.args:
        names.append(arg.arg)
    for arg in node.args.kwonlyargs:
        names.append(arg.arg)
    names = [name for name in names if name not in {"self", "cls"}]
    return names


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
    candidates: list[FunctionInfo] = []
    instance_methods: list[InstanceMethodSpec] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = _function_arg_list_collect(node)
            dependencies = [arg for arg in args if _is_dependency_like(arg)]
            candidates.append(
                FunctionInfo(
                    path=path,
                    lineno=node.lineno,
                    qualname=node.name,
                    name=node.name,
                    module_name=module_name,
                    is_staticmethod=False,
                    dependency_param_list=dependencies,
                    args_count=len(args),
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
                args = _function_arg_list_collect(class_item)
                dependencies = [arg for arg in args if _is_dependency_like(arg)]
                candidates.append(
                    FunctionInfo(
                        path=path,
                        lineno=class_item.lineno,
                        qualname=qualname,
                        name=class_item.name,
                        module_name=module_name,
                        is_staticmethod=True,
                        dependency_param_list=dependencies,
                        args_count=len(args),
                        node=class_item,
                        comment_reason=_comment_reason_get(source_line_list, class_item.lineno),
                    )
                )
            elif not _is_classmethod(class_item):
                instance_methods.append(InstanceMethodSpec(qualname=qualname, node=class_item))

    return ModuleCandidateScanResult(
        function_candidate_list=candidates,
        instance_method_list=instance_methods,
    )


def _module_helper_index_build(candidates: Iterable[FunctionInfo]) -> dict[str, set[str]]:
    """Build helper name index by module.

    Args:
        candidates: Function candidates.

    Returns:
        Mapping module name -> helper bare names.
    """

    index: dict[str, set[str]] = {}
    for item in candidates:
        index.setdefault(item.module_name, set()).add(item.name)
    return index


def _pseudo_method_call_finding_list_build(
    *,
    candidates: Iterable[FunctionInfo],
    module_instance_method_map: Mapping[str, list[InstanceMethodSpec]],
) -> list[Finding]:
    """Detect helper callsites that forward object-field packs.

    Args:
        candidates: Helper candidates.
        module_instance_method_map: Instance methods by module.

    Returns:
        Failure findings for pseudo-method helper calls.
    """

    helper_index = _module_helper_index_build(candidates)
    fails: list[Finding] = []

    for module_name, methods in module_instance_method_map.items():
        helper_names = helper_index.get(module_name, set())
        if not helper_names:
            continue

        for method in methods:
            for call in [n for n in ast.walk(method.node) if isinstance(n, ast.Call)]:
                name = _called_name_get(call)
                if name is None or name not in helper_names:
                    continue

                base_counts = _arg_object_field_count_map_compute(call)
                violating_base = next((base for base, count in base_counts.items() if count >= 2), None)
                if violating_base is None:
                    continue

                fails.append(
                    Finding(
                        level="FAIL",
                        path=Path(module_name),
                        lineno=call.lineno,
                        function_name=method.qualname,
                        reason=(
                            "pseudo-method helper call: 2+ arguments sourced from "
                            f"{violating_base}.* into helper `{name}`; convert helper to method/collaborator"
                        ),
                    )
                )

    return fails


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

    by_module: dict[str, list[FunctionInfo]] = {}
    for item in candidates:
        by_module.setdefault(item.module_name, []).append(item)

    fails: list[Finding] = []
    warns: list[Finding] = []

    for _, module_items in by_module.items():
        for index, left in enumerate(module_items):
            if left.comment_reason is not None:
                continue
            if not left.dependency_param_list:
                continue
            for right in module_items[index + 1 :]:
                if right.comment_reason is not None:
                    continue
                if not right.dependency_param_list:
                    continue
                shared = sorted(set(left.dependency_param_list) & set(right.dependency_param_list))
                if len(shared) < min_shared:
                    continue

                finding = Finding(
                    level="FAIL" if fail_on_repeated_pack else "WARN",
                    path=left.path,
                    lineno=left.lineno,
                    function_name=left.qualname,
                    reason=(
                        "repeated dependency-pack across functions "
                        f"{left.qualname} <-> {right.qualname}; shared={shared}; "
                        "consider collaborator class or private owner method"
                    ),
                )
                if fail_on_repeated_pack:
                    fails.append(finding)
                else:
                    warns.append(finding)

    return FindingSplitResult(fail_finding_list=fails, warn_finding_list=warns)


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

    all_candidates: list[FunctionInfo] = []
    module_methods: dict[str, list[InstanceMethodSpec]] = {}

    for path in scope:
        scan_result = _module_candidate_scan_result_build(path)
        all_candidates.extend(scan_result.function_candidate_list)
        module_methods[path.as_posix()] = scan_result.instance_method_list

    fail_findings: list[Finding] = []
    warn_findings: list[Finding] = []

    argument_explosion_result = _argument_explosion_check_result_build(all_candidates, max_args=args.max_args)
    fail_findings.extend(argument_explosion_result.fail_finding_list)
    warn_findings.extend(argument_explosion_result.warn_finding_list)

    repeated_pack_result = _repeated_pack_check_result_build(
        all_candidates,
        min_shared=args.min_shared,
        fail_on_repeated_pack=args.fail_on_repeated_pack,
    )
    fail_findings.extend(repeated_pack_result.fail_finding_list)
    warn_findings.extend(repeated_pack_result.warn_finding_list)

    fail_findings.extend(
        _pseudo_method_call_finding_list_build(candidates=all_candidates, module_instance_method_map=module_methods)
    )

    if fail_findings:
        print("Python argument-pack violations:")
        for finding in sorted(fail_findings, key=lambda x: (x.path.as_posix(), x.lineno, x.function_name)):
            print(_finding_text_get(finding))
        if warn_findings:
            print("\nPython argument-pack warnings:")
            for finding in sorted(warn_findings, key=lambda x: (x.path.as_posix(), x.lineno, x.function_name)):
                print(_finding_text_get(finding))
        return 1

    if warn_findings:
        print("Python argument-pack warnings:")
        for finding in sorted(warn_findings, key=lambda x: (x.path.as_posix(), x.lineno, x.function_name)):
            print(_finding_text_get(finding))
        print("Python argument-pack check passed with warnings.")
        return 0

    print("Python argument-pack check passed.")
    return 0


@dataclass(frozen=True)
class Finding:
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


@dataclass(frozen=True)
class FindingSplitResult:
    """Represent one split finding collection."""

    fail_finding_list: list[Finding]
    warn_finding_list: list[Finding]


@dataclass(frozen=True)
class FunctionInfo:
    """Represent one helper candidate.

    Args:
        path: Source file path.
        lineno: Definition line number.
        qualname: Qualified function name (`fn`, `Class.fn`).
        name: Bare function name.
        module_name: File-local module identifier.
        is_staticmethod: Whether candidate is `@staticmethod`.
        dependency_param_list: Dependency-like parameter names.
        args_count: Count of explicit named arguments excluding `self`/`cls`.
        node: AST node for the function definition.
        comment_reason: Allow-comment reason text when present.
    """

    args_count: int
    comment_reason: str | None
    dependency_param_list: list[str]
    is_staticmethod: bool
    lineno: int
    module_name: str
    name: str
    node: ast.AST
    path: Path
    qualname: str


@dataclass(frozen=True)
class InstanceMethodSpec:
    """Represent one instance method used for pseudo-method helper checks."""

    node: ast.AST
    qualname: str


@dataclass(frozen=True)
class ModuleCandidateScanResult:
    """Represent one module-level candidate scan."""

    function_candidate_list: list[FunctionInfo]
    instance_method_list: list[InstanceMethodSpec]


if __name__ == "__main__":
    sys.exit(main())
