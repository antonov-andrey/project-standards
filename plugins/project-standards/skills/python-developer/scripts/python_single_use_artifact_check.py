#!/usr/bin/env python3

"""Check forbidden single-use call_wrap and profile artifacts.

Detect top-level call_wrap-shaped functions and thin subclasses, then flag them
when repository usage shows they are effectively single-use artifacts.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import sys

from lib.checker_runtime import TMP_ROOT, main_project_scope_path_list_resolve, scope_args_add
from lib.python_proxy_analysis import (
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

    parser = argparse.ArgumentParser(description="Check forbidden single-use call_wrap/profile artifacts.")
    scope_args_add(
        parser,
        scope_help="Optional explicit Main project Python files/directories. When provided, --scope is ignored.",
    )
    return parser.parse_args()


def _candidate_map_build(scope_path_list: list[Path]) -> dict[CandidateKey, Candidate]:
    """Collect call_wrap/profile candidate_map from the selected scope.

    Args:
        scope_path_list: Candidate-definition scope.

    Returns:
        Mapping `CandidateKey -> candidate`.
    """

    candidate_map: dict[CandidateKey, Candidate] = {}
    for path in scope_path_list:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        module_name = _path_module_name_get(path)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                candidate = _function_candidate_build(path=path, module_name=module_name, node=node)
                if candidate is not None:
                    candidate_map[candidate.key_get()] = candidate
                continue
            if not isinstance(node, ast.ClassDef):
                continue
            if thin_subclass_violation_get(path, node) is None:
                continue
            candidate = Candidate(
                module_name=module_name,
                symbol_name=node.name,
                symbol_kind="class",
                path=path,
                lineno=node.lineno,
                reason="single-use thin subclass/profile call_wrap is forbidden",
            )
            candidate_map[candidate.key_get()] = candidate
    return candidate_map


def _function_candidate_build(
    *,
    path: Path,
    module_name: str,
    node: ast.AST,
) -> Candidate | None:
    """Build candidate for a call_wrap-shaped top-level function.

    Args:
        path: Source file path.
        module_name: Module name owning the function.
        node: Top-level function AST node.

    Returns:
        Candidate when function is call_wrap-shaped, else `None`.
    """

    if node.name in TOP_LEVEL_ALLOWLIST:
        return None
    body = executable_statement_list_collect(node)
    if len(body) != 1:
        return None
    call = delegate_call_get(body[0])
    if call is None:
        return None

    param_list = parameter_name_list_collect(node)
    if is_parameter_forwarding_pure(call, param_list=param_list):
        return Candidate(
            module_name=module_name,
            symbol_name=node.name,
            symbol_kind="function",
            path=path,
            lineno=node.lineno,
            reason="single-use pass-through call_wrap function is forbidden",
        )

    forwarding_result = forwarding_call_analysis_build(call, param_list=param_list)
    if forwarding_result.is_valid and forwarding_result.has_literal and is_probable_constructor_target(call):
        return Candidate(
            module_name=module_name,
            symbol_name=node.name,
            symbol_kind="function",
            path=path,
            lineno=node.lineno,
            reason="single-use thin constructor/profile call_wrap function is forbidden",
        )
    return None


def _imported_module_get(*, current_package: str, module: str | None, level: int) -> str | None:
    """Resolve absolute imported module name for one import statement.

    Args:
        current_package: Package context of the importing module.
        module: Imported module path from AST.
        level: Relative import level.

    Returns:
        Absolute module name, or `None` when resolution escapes the repository package tree.
    """

    if level == 0:
        return module

    package_parts = [part for part in current_package.split(".") if part]
    if level > 1:
        climb = level - 1
        if climb > len(package_parts):
            return None
        package_parts = package_parts[: len(package_parts) - climb]

    target_parts = list(package_parts)
    if module:
        target_parts.extend(part for part in module.split(".") if part)
    if not target_parts:
        return None
    return ".".join(target_parts)


def _path_module_name_get(path: Path) -> str:
    """Convert repository-relative file path to importable module name.

    Args:
        path: Repository-relative Python path.

    Returns:
        Module name.
    """

    module_name = path.with_suffix("").as_posix().replace("/", ".")
    if module_name.endswith(".__init__"):
        return module_name[: -len(".__init__")]
    return module_name


def _path_package_name_get(path: Path) -> str:
    """Return package context for import resolution.

    Args:
        path: Repository-relative Python path.

    Returns:
        Current package name.
    """

    module_name = _path_module_name_get(path)
    if path.name == "__init__.py":
        return module_name
    if "." not in module_name:
        return ""
    return module_name.rsplit(".", 1)[0]


def _usage_count_map_compute(
    candidate_map: dict[CandidateKey, Candidate], *, source_scope_path_list: list[Path]
) -> dict[CandidateKey, int]:
    """Count call-site usages for the selected candidate_map across repo product scope.

    Args:
        candidate_map: Candidate mapping keyed by `(module_name, symbol_name)`.
        source_scope_path_list: Explicit resolved checker scope.

    Returns:
        Mapping from candidate key to call-site usage count.
    """

    counts = {key: 0 for key in candidate_map}
    if not candidate_map:
        return counts

    candidate_key_set = set(candidate_map)
    for path in _usage_search_scope_path_list_build(source_scope_path_list):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        current_module_name = _path_module_name_get(path)
        current_package = _path_package_name_get(path)

        direct_alias_map: dict[str, set[CandidateKey]] = {}
        module_alias_map: dict[str, str] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _imported_module_get = alias.name
                    bound_name = alias.asname or _imported_module_get.split(".")[-1]
                    module_alias_map[bound_name] = _imported_module_get
            elif isinstance(node, ast.ImportFrom):
                imported_module = _imported_module_get(
                    current_package=current_package,
                    module=node.module,
                    level=node.level,
                )
                if imported_module is None:
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate_key = CandidateKey(module_name=imported_module, symbol_name=alias.name)
                    if candidate_key not in candidate_key_set:
                        continue
                    bound_name = alias.asname or alias.name
                    direct_alias_map.setdefault(bound_name, set()).add(candidate_key)

        visitor = UsageVisitor(
            current_module_name=current_module_name,
            direct_alias_map=direct_alias_map,
            module_alias_map=module_alias_map,
            candidate_key_set=candidate_key_set,
        )
        visitor.visit(tree)
        for candidate_key, count in visitor._counts.items():
            counts[candidate_key] = counts.get(candidate_key, 0) + count

    return counts


def _usage_search_scope_path_list_build(source_scope_path_list: list[Path]) -> list[Path]:
    """Choose the call-site counting scope for candidate usage analysis.

    Repository candidate_map keep repo-wide usage counting. Owner-local test
    sample files under `/tmp/**` count usages only within the selected explicit
    sample scope.

    Args:
        source_scope_path_list: Explicit resolved checker scope.

    Returns:
        Python files that should participate in call-site counting.
    """

    if any(path.is_absolute() and path.is_relative_to(TMP_ROOT) for path in source_scope_path_list):
        return source_scope_path_list
    return main_project_scope_path_list_resolve([], "all")


def main() -> int:
    """Run single-use call_wrap/profile checker.

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
        print("INFO: single-use artifact check skipped (no Python files in scope).")
        return 0

    candidate_map = _candidate_map_build(scope)
    if not candidate_map:
        print("Python single-use artifact check passed.")
        return 0

    counts = _usage_count_map_compute(candidate_map, source_scope_path_list=scope)
    violations: list[str] = []
    for candidate_key, candidate in sorted(
        candidate_map.items(), key=lambda item: (item[1].path.as_posix(), item[1].lineno)
    ):
        use_count = counts.get(candidate_key, 0)
        if use_count > 1:
            continue
        violations.append(
            f"{candidate.path}:{candidate.lineno} {candidate.symbol_kind} {candidate.symbol_name}: "
            f"{candidate.reason} (repo call-site count={use_count})"
        )

    if violations:
        print("Python single-use call_wrap/profile violations:")
        for violation in violations:
            print(violation)
        return 1

    print("Python single-use artifact check passed.")
    return 0


@dataclass(frozen=True)
class Candidate:
    """Represent one single-use call_wrap/profile candidate."""

    lineno: int
    module_name: str
    path: Path
    reason: str
    symbol_kind: str
    symbol_name: str

    def key_get(self) -> "CandidateKey":
        """Return the identity key used by usage counting.

        Returns:
            Stable candidate identity key.
        """

        return CandidateKey(module_name=self.module_name, symbol_name=self.symbol_name)


@dataclass(frozen=True)
class CandidateKey:
    """Represent one candidate symbol identity key."""

    module_name: str
    symbol_name: str


class UsageVisitor(ast.NodeVisitor):
    """Collect call-site usages for candidate symbols in one module."""

    def __init__(
        self,
        *,
        current_module_name: str,
        direct_alias_map: dict[str, set[CandidateKey]],
        module_alias_map: dict[str, str],
        candidate_key_set: set[CandidateKey],
    ) -> None:
        """Initialize usage visitor state.

        Args:
            current_module_name: Module name currently being traversed.
            direct_alias_map: Imported direct symbol aliases visible in the module.
            module_alias_map: Imported module aliases visible in the module.
            candidate_key_set: Candidate symbol keys tracked for usage counting.
        """

        self._current_module_name = current_module_name
        self._direct_aliases = direct_alias_map
        self._module_aliases = module_alias_map
        self._candidate_keys = candidate_key_set
        self._counts: dict[CandidateKey, int] = {}

    def visit_Call(self, node: ast.Call) -> None:
        """Collect call_wrap/profile call-site usage from one call node.

        Args:
            node: Current call node being visited.
        """

        func = node.func
        if isinstance(func, ast.Name):
            direct_candidates = self._direct_aliases.get(func.id, set())
            if direct_candidates:
                for candidate_key in direct_candidates:
                    self._counts[candidate_key] = self._counts.get(candidate_key, 0) + 1
            else:
                candidate_key = CandidateKey(module_name=self._current_module_name, symbol_name=func.id)
                if candidate_key in self._candidate_keys:
                    self._counts[candidate_key] = self._counts.get(candidate_key, 0) + 1
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            module_name = self._module_aliases.get(func.value.id)
            if module_name is not None:
                candidate_key = CandidateKey(module_name=module_name, symbol_name=func.attr)
                if candidate_key in self._candidate_keys:
                    self._counts[candidate_key] = self._counts.get(candidate_key, 0) + 1
        self.generic_visit(node)


if __name__ == "__main__":
    sys.exit(main())
