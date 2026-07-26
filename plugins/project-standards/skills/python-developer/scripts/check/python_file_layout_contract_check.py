#!/usr/bin/env python3
"""Check canonical top-level Python file layout and dependency-aware order."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from pathlib import Path
import re
import sys
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_syntax import import_group_name_get, repository_module_root_name_set_get

DIRECT_PACKAGE_BOOTSTRAP_RE = re.compile(
    r'^sys\.path\.insert\(0, str\(Path\(__file__\)\.resolve\(\)\.parents\[\d+\] / "lib"\)\)$'
)


def _assigned_name_get(node: ast.stmt) -> str | None:
    """Return one simply assigned module-level name.

    Args:
        node: Candidate assignment.

    Returns:
        Assigned name when the target shape is unambiguous.
    """

    if isinstance(node, ast.Assign):
        return node.targets[0].id if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) else None
    return node.target.id if isinstance(node.target, ast.Name) else None


def _consumer_name_set_by_private_function_name_map_get(module_node: ast.Module) -> dict[str, set[str]]:
    """Return public consumers reachable through private helper calls.

    Args:
        module_node: Parsed module.

    Returns:
        Public consumer names keyed by private module-level function name.
    """

    top_level_node_by_name_map: dict[str, ast.AST] = {}
    public_consumer_name_set: set[str] = set()
    consumer_name_set_by_private_function_name_map: dict[str, set[str]] = {}
    for node in module_node.body:
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            top_level_node_by_name_map[node.name] = node
            if _is_private_name_match(node.name):
                consumer_name_set_by_private_function_name_map[node.name] = set()
            else:
                public_consumer_name_set.add(node.name)
        elif isinstance(node, ast.ClassDef):
            top_level_node_by_name_map[node.name] = node
            public_consumer_name_set.add(node.name)
    reference_name_set_by_name_map = {
        name: {
            child_node.id
            for child_node in ast.walk(node)
            if isinstance(child_node, ast.Name) and isinstance(child_node.ctx, ast.Load)
        }
        for name, node in top_level_node_by_name_map.items()
    }
    for consumer_name in public_consumer_name_set:
        pending_name_list = [consumer_name]
        seen_name_set = {consumer_name}
        while pending_name_list:
            current_name = pending_name_list.pop()
            for reference_name in reference_name_set_by_name_map.get(current_name, set()):
                if reference_name not in top_level_node_by_name_map or reference_name in seen_name_set:
                    continue
                seen_name_set.add(reference_name)
                pending_name_list.append(reference_name)
                if reference_name in consumer_name_set_by_private_function_name_map:
                    consumer_name_set_by_private_function_name_map[reference_name].add(consumer_name)
    return consumer_name_set_by_private_function_name_map


def _dependency_aware_name_list_get(
    dependency_name_set_by_name_map: Mapping[str, set[str]],
    name_list: list[str],
) -> list[str] | None:
    """Return dependency-aware alphabetical order for one item block.

    Args:
        dependency_name_set_by_name_map: Direct eager dependencies keyed by item.
        name_list: Block member names.

    Returns:
        Canonical order, or `None` for one eager dependency cycle.
    """

    dependent_name_set_by_name_map = {name: set() for name in name_list}
    remaining_dependency_name_set_by_name_map = {
        name: set(dependency_name_set_by_name_map.get(name, set())) for name in name_list
    }
    for consumer_name, dependency_name_set in remaining_dependency_name_set_by_name_map.items():
        for dependency_name in dependency_name_set:
            dependent_name_set_by_name_map[dependency_name].add(consumer_name)
    ordered_name_list: list[str] = []
    ready_name_list = sorted(name for name in name_list if not remaining_dependency_name_set_by_name_map[name])
    while ready_name_list:
        current_name = ready_name_list.pop(0)
        ordered_name_list.append(current_name)
        for dependent_name in sorted(dependent_name_set_by_name_map[current_name]):
            remaining_dependency_name_set_by_name_map[dependent_name].discard(current_name)
            if not remaining_dependency_name_set_by_name_map[dependent_name]:
                ready_name_list.append(dependent_name)
        ready_name_list.sort()
    return ordered_name_list if len(ordered_name_list) == len(name_list) else None


def _direct_eager_reference_name_set_get(node: ast.AST) -> set[str]:
    """Return names evaluated eagerly for one module-level definition.

    Args:
        node: Candidate definition or assignment.

    Returns:
        Names loaded by decorators, bases, and default expressions.
    """

    class EagerReferenceCollector(ast.NodeVisitor):
        """Collect load references evaluated while a module imports."""

        def __init__(self) -> None:
            """Initialize one empty eager-reference set."""

            self.name_set: set[str] = set()

        def visit_AnnAssign(self, child_node: ast.AnnAssign) -> None:
            """Visit only the runtime value of an annotated assignment.

            Args:
                child_node: Candidate assignment.
            """

            if child_node.value is not None:
                self.visit(child_node.value)

        def visit_AsyncFunctionDef(self, child_node: ast.AsyncFunctionDef) -> None:
            """Visit eager parts of one async function definition.

            Args:
                child_node: Candidate async function.
            """

            self._function_eager_visit(child_node)

        def visit_ClassDef(self, child_node: ast.ClassDef) -> None:
            """Visit eager decorators, bases, keywords, and class body.

            Args:
                child_node: Candidate class.
            """

            for decorator_node in child_node.decorator_list:
                self.visit(decorator_node)
            for base_node in child_node.bases:
                self.visit(base_node)
            for keyword_node in child_node.keywords:
                self.visit(keyword_node.value)
            for statement_node in child_node.body:
                self.visit(statement_node)

        def visit_FunctionDef(self, child_node: ast.FunctionDef) -> None:
            """Visit eager parts of one function definition.

            Args:
                child_node: Candidate function.
            """

            self._function_eager_visit(child_node)

        def visit_Lambda(self, child_node: ast.Lambda) -> None:
            """Skip lambda bodies because they are not eagerly executed.

            Args:
                child_node: Candidate lambda.
            """

        def visit_Name(self, child_node: ast.Name) -> None:
            """Record one eager load reference.

            Args:
                child_node: Candidate name.
            """

            if isinstance(child_node.ctx, ast.Load):
                self.name_set.add(child_node.id)

        def _function_eager_visit(
            self,
            child_node: ast.stmt,
        ) -> None:
            """Visit decorators and defaults of one function.

            Args:
                child_node: Candidate callable.
            """

            for decorator_node in child_node.decorator_list:
                self.visit(decorator_node)
            for default_node in child_node.args.defaults:
                self.visit(default_node)
            for default_node in child_node.args.kw_defaults:
                if default_node is not None:
                    self.visit(default_node)

    collector = EagerReferenceCollector()
    collector.visit(node)
    return collector.name_set


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return canonical file-layout findings.

    Args:
        request: Validated checker request.

    Returns:
        Findings across non-Legacy production Python.
    """

    project_root = Path(request["project_root"])
    eligible_relative_path_set = set(non_legacy_non_test_python_relpath_list_get(project_root, scope="all"))
    repository_module_root_name_set = repository_module_root_name_set_get(project_root)
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if relative_path not in eligible_relative_path_set or not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        try:
            module_node = ast.parse(source, filename=relative_path)
        except SyntaxError:
            continue
        finding_list.extend(
            _module_finding_list_get(
                module_node,
                relative_path,
                repository_module_root_name_set,
                source.splitlines(),
            )
        )
    return finding_list


def _import_module_name_list_get(node: ast.stmt) -> list[str]:
    """Return imported module paths used for ordering one statement.

    Args:
        node: Candidate import statement.

    Returns:
        Ordered module path list.
    """

    if isinstance(node, ast.Import):
        return [alias_node.name for alias_node in node.names]
    return ["." * node.level + (node.module or "")]


def _is_private_name_match(name: str) -> bool:
    """Return whether one name is private but not dunder.

    Args:
        name: Candidate name.

    Returns:
        Whether the name uses one private leading underscore.
    """

    return name.startswith("_") and not name.startswith("__")


def _is_tool_import_bootstrap_gap_match(
    left_group_name: str,
    line_between_list: list[str],
    relative_path: str,
    right_group_name: str,
) -> bool:
    """Return whether one import gap is a canonical script bootstrap.

    Args:
        left_group_name: Import group before the bootstrap.
        line_between_list: Raw source lines in the gap.
        relative_path: Repository-relative source path.
        right_group_name: Import group after the bootstrap.

    Returns:
        Whether the gap is one approved source-import path setup.
    """

    if left_group_name not in {"stdlib", "third_party"} or right_group_name != "repository_local":
        return False
    if not any(part in Path(relative_path).parts for part in {"scripts", "tool"}):
        return False
    nonempty_line_list = [line.strip() for line in line_between_list if line.strip()]
    if len(nonempty_line_list) == 1 and DIRECT_PACKAGE_BOOTSTRAP_RE.fullmatch(nonempty_line_list[0]):
        return True
    canonical_repository_root_block_list = [
        "for parent in Path(__file__).resolve().parents:",
        'if not (parent / ".gitmodules").exists():',
        "continue",
        "if str(parent) not in sys.path:",
        "sys.path.insert(0, str(parent))",
        "break",
    ]
    optional_local_lib_block_list = [
        "if str(Path(__file__).resolve().parents[1]) not in sys.path:",
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))",
    ]
    return nonempty_line_list in (
        canonical_repository_root_block_list,
        [*optional_local_lib_block_list, *canonical_repository_root_block_list],
    )


def _module_finding_list_get(
    module_node: ast.Module,
    relative_path: str,
    repository_module_root_name_set: set[str],
    source_line_list: Sequence[str],
) -> list[ProjectStandardCheckerFinding]:
    """Return all file-layout findings for one parsed module.

    Args:
        module_node: Parsed module.
        relative_path: Repository-relative source path.
        repository_module_root_name_set: Repository-owned import roots.
        source_line_list: Raw source split into lines.

    Returns:
        Import, top-level order, block-order, and helper-placement findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    top_level_item_list = _top_level_item_list_get(module_node)
    import_item_list = [item for item in top_level_item_list if item["kind"] == "import"]
    if import_item_list:
        import_group_rank_by_name_map = {"repository_local": 2, "stdlib": 0, "third_party": 1}
        import_group_name_list = [
            import_group_name_get(item["node"], repository_module_root_name_set)
            for item in import_item_list
            if isinstance(item["node"], (ast.Import, ast.ImportFrom))
        ]
        if any(
            import_group_rank_by_name_map[left_group_name] > import_group_rank_by_name_map[right_group_name]
            for left_group_name, right_group_name in zip(import_group_name_list, import_group_name_list[1:])
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    message="import groups are not ordered stdlib -> third_party -> repository_local",
                    path=relative_path,
                )
            )
        for left_item, left_group_name, right_item, right_group_name in zip(
            import_item_list,
            import_group_name_list,
            import_item_list[1:],
            import_group_name_list[1:],
        ):
            if left_group_name == right_group_name:
                continue
            line_between_list = source_line_list[left_item["end_lineno"] : right_item["lineno"] - 1]
            blank_line_count = sum(1 for line in line_between_list if not line.strip())
            if blank_line_count != 1 and not _is_tool_import_bootstrap_gap_match(
                left_group_name,
                line_between_list,
                relative_path,
                right_group_name,
            ):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=right_item["lineno"],
                        message="import groups must be separated by exactly one blank line",
                        path=relative_path,
                    )
                )
        import_item_list_by_group_name_map: dict[str, list[TopLevelItem]] = {}
        for item, group_name in zip(import_item_list, import_group_name_list):
            import_item_list_by_group_name_map.setdefault(group_name, []).append(item)
            node = item["node"]
            if not isinstance(node, ast.ImportFrom):
                continue
            alias_name_list = [alias_node.name for alias_node in node.names if alias_node.name != "*"]
            if alias_name_list != sorted(alias_name_list):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=item["lineno"],
                        message="imported names inside one from-import statement must be sorted",
                        path=relative_path,
                    )
                )
        for group_item_list in import_item_list_by_group_name_map.values():
            import_module_name_list = [_import_module_name_list_get(item["node"]) for item in group_item_list]
            if import_module_name_list != sorted(import_module_name_list):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=group_item_list[0]["lineno"],
                        message="import statements inside one group must be sorted",
                        path=relative_path,
                    )
                )
    item_rank_by_kind_map = {
        "class_block": 4,
        "constant": 1,
        "import": 0,
        "module_variable": 2,
        "public_function": 3,
    }
    ordered_item_list = [item for item in top_level_item_list if item["kind"] in item_rank_by_kind_map]
    if any(
        item_rank_by_kind_map[left_item["kind"]] > item_rank_by_kind_map[right_item["kind"]]
        for left_item, right_item in zip(ordered_item_list, ordered_item_list[1:])
    ):
        finding_list.append(
            ProjectStandardCheckerFinding(
                message=(
                    "top-level order must be import groups -> constants -> module variables -> public functions "
                    "-> class blocks"
                ),
                path=relative_path,
            )
        )
    for item_kind in ("constant", "module_variable", "public_function", "class_block"):
        same_kind_item_list = [item for item in ordered_item_list if item["kind"] == item_kind]
        actual_name_list = [item["name"] for item in same_kind_item_list]
        expected_name_list = _dependency_aware_name_list_get(
            _same_kind_eager_dependency_name_set_by_name_map_get(same_kind_item_list),
            actual_name_list,
        )
        if expected_name_list is None or actual_name_list != expected_name_list:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    message=(
                        f"{item_kind.replace('_', ' ')} items must follow dependency-aware alphabetical order; "
                        f"expected {expected_name_list}"
                    ),
                    path=relative_path,
                )
            )
    for left_item, right_item in zip(top_level_item_list, top_level_item_list[1:]):
        if {left_item["kind"], right_item["kind"]} - {"constant", "module_variable"}:
            continue
        blank_line_count = sum(
            1 for line in source_line_list[left_item["end_lineno"] : right_item["lineno"] - 1] if not line.strip()
        )
        if left_item["kind"] == right_item["kind"] and blank_line_count != 0:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=right_item["lineno"],
                    message=f"adjacent {left_item['kind'].replace('_', ' ')} items must not have blank lines",
                    path=relative_path,
                )
            )
        if left_item["kind"] != right_item["kind"] and blank_line_count != 1:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=right_item["lineno"],
                    message="constants and module variables must be separated by exactly one blank line",
                    path=relative_path,
                )
            )
    consumer_name_set_by_private_function_name_map = _consumer_name_set_by_private_function_name_map_get(module_node)
    top_level_index_by_name_map = {item["name"]: index for index, item in enumerate(top_level_item_list)}
    top_level_item_by_name_map = {item["name"]: item for item in top_level_item_list}
    private_function_name_list_by_consumer_name_map: dict[str, list[str]] = {}
    for private_function_name, consumer_name_set in consumer_name_set_by_private_function_name_map.items():
        if not consumer_name_set:
            continue
        first_consumer_name = min(
            consumer_name_set,
            key=lambda name: top_level_index_by_name_map[name],
        )
        private_function_name_list_by_consumer_name_map.setdefault(first_consumer_name, []).append(
            private_function_name
        )
    for consumer_name, private_function_name_list in private_function_name_list_by_consumer_name_map.items():
        consumer_index = top_level_index_by_name_map[consumer_name]
        expected_private_function_name_list = _dependency_aware_name_list_get(
            _same_kind_eager_dependency_name_set_by_name_map_get(
                [top_level_item_by_name_map[name] for name in private_function_name_list]
            ),
            private_function_name_list,
        )
        actual_private_function_name_list: list[str] = []
        index = consumer_index - 1
        while index >= 0 and top_level_item_list[index]["kind"] == "private_function":
            actual_private_function_name_list.insert(0, top_level_item_list[index]["name"])
            index -= 1
        if expected_private_function_name_list != actual_private_function_name_list:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=top_level_item_list[consumer_index]["lineno"],
                    message=(
                        f"private helper block before {consumer_name} must be exactly "
                        f"{expected_private_function_name_list}"
                    ),
                    path=relative_path,
                )
            )
    return finding_list


def _same_kind_eager_dependency_name_set_by_name_map_get(
    item_list: list[TopLevelItem],
) -> dict[str, set[str]]:
    """Return same-kind eager dependency names for one block.

    Args:
        item_list: Same-kind module-level items.

    Returns:
        Direct eager dependencies keyed by item name.
    """

    item_name_set = {item["name"] for item in item_list}
    dependency_name_set_by_name_map: dict[str, set[str]] = {}
    for item in item_list:
        dependency_name_set = _direct_eager_reference_name_set_get(item["node"]) & item_name_set
        dependency_name_set.discard(item["name"])
        dependency_name_set_by_name_map[item["name"]] = dependency_name_set
    return dependency_name_set_by_name_map


def _top_level_item_list_get(module_node: ast.Module) -> list[TopLevelItem]:
    """Return module-level items relevant to canonical layout.

    Args:
        module_node: Parsed module.

    Returns:
        Items in lexical source order.
    """

    item_list: list[TopLevelItem] = []
    for node in module_node.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            item_list.append(
                TopLevelItem(
                    end_lineno=node.end_lineno or node.lineno,
                    kind="import",
                    lineno=node.lineno,
                    name=ast.unparse(node),
                    node=node,
                )
            )
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        elif isinstance(node, (ast.AnnAssign, ast.Assign)):
            assigned_name = _assigned_name_get(node)
            if assigned_name is not None:
                item_list.append(
                    TopLevelItem(
                        end_lineno=node.end_lineno or node.lineno,
                        kind="constant" if assigned_name.isupper() else "module_variable",
                        lineno=node.lineno,
                        name=assigned_name,
                        node=node,
                    )
                )
        elif isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            item_list.append(
                TopLevelItem(
                    end_lineno=node.end_lineno or node.lineno,
                    kind="private_function" if _is_private_name_match(node.name) else "public_function",
                    lineno=node.lineno,
                    name=node.name,
                    node=node,
                )
            )
        elif isinstance(node, ast.ClassDef):
            item_list.append(
                TopLevelItem(
                    end_lineno=node.end_lineno or node.lineno,
                    kind="class_block",
                    lineno=node.lineno,
                    name=node.name,
                    node=node,
                )
            )
    return item_list


def main() -> int:
    """Run canonical Python file-layout checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


class TopLevelItem(TypedDict):
    """Describe one module-level item relevant to file layout."""

    end_lineno: int
    kind: str
    lineno: int
    name: str
    node: ast.AST


if __name__ == "__main__":
    raise SystemExit(main())
