#!/usr/bin/env python3
"""Check method visibility through Jedi-resolved receiver use sites."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
import sys

import jedi

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.git_repository import submodule_name_by_path_map_get
from project_standards.project_scope import (
    non_legacy_non_test_python_outside_submodule_relpath_list_get,
    python_relpath_list_get,
)
from project_standards.project_standard_model import (
    ProjectStandardCheckerFinding,
    ProjectStandardPythonMethodDefinition,
    ProjectStandardPythonMethodUse,
    ProjectStandardRequest,
)
from project_standards.python_import import module_name_get
from project_standards.python_syntax import call_name_get

JEDI_SCRIPT_RESOLUTION_BATCH_SIZE = 32


def _class_fqn_by_line_map_get(
    module_node: ast.Module,
    module_name: str,
) -> dict[int, str]:
    """Return top-level owner class FQNs keyed by covered line.

    Args:
        module_node: Parsed module.
        module_name: Current dotted module name.

    Returns:
        Line-to-class map for top-level class bodies.
    """

    class_fqn_by_line_map: dict[int, str] = {}
    for class_node in module_node.body:
        if not isinstance(class_node, ast.ClassDef):
            continue
        class_fqn = f"{module_name}.{class_node.name}"
        for line in range(class_node.lineno, (class_node.end_lineno or class_node.lineno) + 1):
            class_fqn_by_line_map[line] = class_fqn
    return class_fqn_by_line_map


def _decorator_name_set_get(function_node: ast.stmt) -> set[str]:
    """Return visible decorator names for one method.

    Args:
        function_node: Candidate method.

    Returns:
        Direct decorator tokens.
    """

    return {
        decorator_name
        for decorator_node in function_node.decorator_list
        if (decorator_name := call_name_get(decorator_node)) is not None
    }


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return public-demotion and private-promotion method findings.

    Args:
        request: Validated checker request.

    Returns:
        Findings based on real cross-class receiver uses.
    """

    project_root = Path(request["project_root"])
    submodule_relative_path_list = list(submodule_name_by_path_map_get(project_root))
    production_use_relative_path_list = [
        relative_path
        for relative_path in python_relpath_list_get(project_root, scope="all")
        if not _is_under_submodule_match(relative_path, submodule_relative_path_list)
        and "test" not in Path(relative_path).parts
        and relative_path != "conftest.py"
    ]
    definition_relative_path_list = non_legacy_non_test_python_outside_submodule_relpath_list_get(
        project_root,
        scope="all",
    )
    definition_by_fqn_map = _method_definition_by_fqn_map_get(
        project_root,
        definition_relative_path_list,
    )
    method_use_list_by_fqn_map = _method_use_list_by_fqn_map_get(
        project_root,
        production_use_relative_path_list,
        definition_by_fqn_map,
    )
    requested_path_set = set(request["path_list"])
    finding_list: list[ProjectStandardCheckerFinding] = []
    for method_fqn, definition in sorted(definition_by_fqn_map.items()):
        if definition["path"] not in requested_path_set:
            continue
        external_use_list = [
            use
            for use in method_use_list_by_fqn_map.get(method_fqn, [])
            if use["owner_class_fqn"] != definition["class_fqn"]
        ]
        if _is_private_name_match(definition["method_name"]):
            if not external_use_list:
                continue
            use_text = ", ".join(
                f"{use['path']}:{use['line']} ({use['owner_class_fqn'] or 'module scope'})"
                for use in sorted(
                    external_use_list,
                    key=lambda use: (use["path"], use["line"], use["owner_class_fqn"] or ""),
                )
            )
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=definition["line"],
                    message=(
                        f"private method {definition['class_name']}.{definition['method_name']} is used outside "
                        f"its class by {use_text}; promote it"
                    ),
                    path=definition["path"],
                )
            )
            continue
        if _match_external_contract_visibility(definition) or external_use_list:
            continue
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=definition["line"],
                message=(
                    f"public method {definition['class_name']}.{definition['method_name']} has no real use site "
                    "outside its class; make it private"
                ),
                path=definition["path"],
            )
        )
    return finding_list


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


def _match_external_contract_visibility(definition: ProjectStandardPythonMethodDefinition) -> bool:
    """Return whether one method shape is owned by an external contract.

    Args:
        definition: Candidate method definition.

    Returns:
        Whether explicit framework or constructor semantics require visibility.
    """

    method_name = definition["method_name"]
    base_name_set = definition["class_base_name_set"]
    decorator_name_set = definition["decorator_name_set"]
    if method_name.startswith("__") and method_name.endswith("__"):
        return True
    if method_name.startswith("visit_") and base_name_set & {"NodeTransformer", "NodeVisitor"}:
        return True
    if (
        method_name.startswith(("from_", "_from_"))
        and "classmethod" in decorator_name_set
        and definition["return_annotation_name"] in {definition["class_name"], "Self"}
    ):
        return True
    if method_name == "support_object_list_get" and "Database" in base_name_set:
        return True
    if method_name == "orm_constructor_kwargs_validate" and "OrmBase" in base_name_set:
        return True
    if decorator_name_set & {
        "abstractmethod",
        "cached_property",
        "field_serializer",
        "field_validator",
        "model_serializer",
        "model_validator",
        "override",
        "overload",
        "property",
        "root_validator",
        "validator",
    }:
        return True
    return method_name.startswith("model_") and bool(base_name_set & {"BaseModel", "BaseModelStrict"})


def _method_definition_by_fqn_map_get(
    project_root: Path,
    definition_relative_path_list: list[str],
) -> dict[str, ProjectStandardPythonMethodDefinition]:
    """Return top-level class methods keyed by FQN.

    Args:
        project_root: Exact repository root.
        definition_relative_path_list: Root-owner definition paths.

    Returns:
        Method definitions keyed by class and method name.
    """

    definition_by_fqn_map: dict[str, ProjectStandardPythonMethodDefinition] = {}
    for relative_path in definition_relative_path_list:
        try:
            module_node = ast.parse(
                (project_root / relative_path).read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except OSError, SyntaxError:
            continue
        module_name = module_name_get(relative_path)
        for class_node in module_node.body:
            if not isinstance(class_node, ast.ClassDef):
                continue
            class_fqn = f"{module_name}.{class_node.name}"
            base_name_set = {
                base_node.id if isinstance(base_node, ast.Name) else base_node.attr
                for base_node in class_node.bases
                if isinstance(base_node, (ast.Attribute, ast.Name))
            }
            for method_node in class_node.body:
                if not isinstance(method_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                    continue
                return_annotation_name = _return_annotation_name_get(method_node.returns)
                method_fqn = f"{class_fqn}.{method_node.name}"
                definition_by_fqn_map[method_fqn] = ProjectStandardPythonMethodDefinition(
                    class_base_name_set=base_name_set,
                    class_fqn=class_fqn,
                    class_name=class_node.name,
                    decorator_name_set=_decorator_name_set_get(method_node),
                    line=method_node.lineno,
                    method_name=method_node.name,
                    path=relative_path,
                    return_annotation_name=return_annotation_name,
                )
    return definition_by_fqn_map


def _method_use_list_by_fqn_map_get(
    project_root: Path,
    production_use_relative_path_list: list[str],
    definition_by_fqn_map: Mapping[str, ProjectStandardPythonMethodDefinition],
) -> dict[str, list[ProjectStandardPythonMethodUse]]:
    """Return Jedi-resolved method uses keyed by method FQN.

    Args:
        project_root: Exact repository root.
        production_use_relative_path_list: Production Python use scope.
        definition_by_fqn_map: Repository method definitions.

    Returns:
        Resolved use records grouped by method FQN.
    """

    class_fqn_set = {definition["class_fqn"] for definition in definition_by_fqn_map.values()}
    method_name_set_by_class_fqn_map: dict[str, set[str]] = {}
    for definition in definition_by_fqn_map.values():
        method_name_set_by_class_fqn_map.setdefault(definition["class_fqn"], set()).add(definition["method_name"])
    candidate_method_name_set = {definition["method_name"] for definition in definition_by_fqn_map.values()}
    project = jedi.Project(path=str(project_root))
    method_use_list_by_fqn_map: dict[str, list[ProjectStandardPythonMethodUse]] = {}
    use_key_set_by_method_fqn_map: dict[str, set[str]] = {}
    for relative_path in production_use_relative_path_list:
        try:
            module_node = ast.parse(
                (project_root / relative_path).read_text(encoding="utf-8"),
                filename=relative_path,
            )
        except OSError, SyntaxError:
            continue
        script = jedi.Script(path=str(project_root / relative_path), project=project)
        script_resolution_count = 0
        class_fqn_by_line_map = _class_fqn_by_line_map_get(module_node, module_name_get(relative_path))
        for node in ast.walk(module_node):
            if (
                not isinstance(node, ast.Attribute)
                or not isinstance(node.ctx, ast.Load)
                or node.attr not in candidate_method_name_set
            ):
                continue
            if script_resolution_count == JEDI_SCRIPT_RESOLUTION_BATCH_SIZE:
                script = jedi.Script(path=str(project_root / relative_path), project=project)
                script_resolution_count = 0
            script_resolution_count += 1
            owner_class_fqn = class_fqn_by_line_map.get(node.lineno)
            inferred_method_fqn_set = {
                name.full_name
                for name in script.goto(
                    node.end_lineno or node.lineno,
                    node.end_col_offset or node.col_offset + 1,
                    follow_builtin_imports=False,
                    follow_imports=True,
                )
                if name.full_name is not None
                and name.full_name.rsplit(".", maxsplit=1)[0] in class_fqn_set
                and name.full_name.rsplit(".", maxsplit=1)[-1] == node.attr
            }
            if len(inferred_method_fqn_set) == 1:
                method_fqn = next(iter(inferred_method_fqn_set))
            else:
                receiver_class_fqn = _receiver_class_fqn_get(
                    class_fqn_set,
                    method_name_set_by_class_fqn_map,
                    node,
                    owner_class_fqn,
                    script,
                )
                if receiver_class_fqn is None:
                    continue
                method_fqn = f"{receiver_class_fqn}.{node.attr}"
            use_key = f"{owner_class_fqn or ''}\0{relative_path}\0{node.lineno}"
            if use_key in use_key_set_by_method_fqn_map.setdefault(method_fqn, set()):
                continue
            use_key_set_by_method_fqn_map[method_fqn].add(use_key)
            method_use_list_by_fqn_map.setdefault(method_fqn, []).append(
                ProjectStandardPythonMethodUse(
                    line=node.lineno,
                    owner_class_fqn=owner_class_fqn,
                    path=relative_path,
                )
            )
    return method_use_list_by_fqn_map


def _receiver_class_fqn_get(
    class_fqn_set: set[str],
    method_name_set_by_class_fqn_map: Mapping[str, set[str]],
    node: ast.Attribute,
    owner_class_fqn: str | None,
    script: jedi.Script,
) -> str | None:
    """Return one uniquely resolved repository-local receiver class.

    Args:
        class_fqn_set: Repository-local class FQNs.
        method_name_set_by_class_fqn_map: Method names keyed by receiver class.
        node: Candidate method attribute access.
        owner_class_fqn: Enclosing class FQN when present.
        script: Jedi script for the current module.

    Returns:
        Receiver class FQN when resolution is unique and owns the method.
    """

    if isinstance(node.value, ast.Name) and owner_class_fqn is not None:
        if node.value.id in {"self", "cls", owner_class_fqn.rsplit(".", maxsplit=1)[-1]}:
            return (
                owner_class_fqn if node.attr in method_name_set_by_class_fqn_map.get(owner_class_fqn, set()) else None
            )
    inferred_class_fqn_set = {
        name.full_name
        for name in script.infer(
            node.value.end_lineno or node.value.lineno,
            node.value.end_col_offset or node.value.col_offset + 1,
        )
        if name.full_name in class_fqn_set
    }
    if len(inferred_class_fqn_set) != 1:
        return None
    receiver_class_fqn = next(iter(inferred_class_fqn_set))
    return receiver_class_fqn if node.attr in method_name_set_by_class_fqn_map.get(receiver_class_fqn, set()) else None


def _return_annotation_name_get(annotation_node: ast.expr | None) -> str | None:
    """Return one direct return-annotation name.

    Args:
        annotation_node: Candidate return annotation.

    Returns:
        Direct name, attribute tail, or `None` for a container or malformed value.
    """

    if isinstance(annotation_node, ast.Constant) and isinstance(annotation_node.value, str):
        try:
            annotation_node = ast.parse(annotation_node.value, mode="eval").body
        except SyntaxError:
            return None
    if isinstance(annotation_node, ast.Name):
        return annotation_node.id
    return annotation_node.attr if isinstance(annotation_node, ast.Attribute) else None


def main() -> int:
    """Run method-visibility checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
