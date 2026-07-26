#!/usr/bin/env python3
"""Check typed Python names, callable names, and collection carrier identity."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_outside_submodule_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest
from project_standards.python_syntax import call_name_get

BOOL_PREFIX_TUPLE = (
    "is_",
    "have_",
    "can_",
    "should_",
    "must_",
    "need_",
    "support_",
    "match_",
    "contain_",
    "exist_",
)
DICT_ROOT_NAME_SET = {"Mapping", "dict"}
HTTP_HEADER_MAP_NAME_SET = {"request_header_map", "response_header_map"}
INHERITED_CALLABLE_NAME_BY_OWNER_MAP = {
    "ProductOrmBase": {"orm_constructor_kwargs_validate"},
    "S3ObjectVersionRangeReader": {"readable", "seekable"},
}
JSON_OBJECT_BOUNDARY_CALLABLE_ACTION_SUFFIX_TUPLE = (
    "_create",
    "_delete",
    "_ensure",
    "_get",
    "_merge_patch",
    "_patch",
    "_post",
    "_put",
    "_request",
)
JSON_OBJECT_BOUNDARY_NAME_SET = {"document", "metadata", "payload"}
JSON_OBJECT_BOUNDARY_SUFFIX_TUPLE = ("_document", "_json", "_metadata", "_payload")
LIST_ROOT_NAME_SET = {"Sequence", "list"}
NUMERIC_SUFFIX_TUPLE = ("_count", "_index", "_number")
TRANSPARENT_WRAPPER_NAME_SET = {"Annotated", "ClassVar", "Final", "Mapped", "NotRequired", "Required"}


def _annotation_node_get(node: ast.AST | None) -> ast.AST | None:
    """Return one normalized annotation syntax node.

    Args:
        node: Raw or quoted annotation node.

    Returns:
        Parsed annotation node when available.
    """

    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return node
    try:
        return ast.parse(node.value, mode="eval").body
    except SyntaxError:
        return None


def _annotation_root_name_get(node: ast.AST | None) -> str | None:
    """Return one canonical annotation root through transparent optional wrappers.

    Args:
        node: Candidate annotation node.

    Returns:
        Stable non-None root name when one exists.
    """

    node = _annotation_node_get(node)
    if node is None:
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        branch_root_name_set = {
            branch_root_name
            for branch_node in (node.left, node.right)
            if not _is_none_annotation_match(branch_node)
            if (branch_root_name := _annotation_root_name_get(branch_node)) is not None
        }
        return next(iter(branch_root_name_set)) if len(branch_root_name_set) == 1 else None
    root_name = _annotation_visible_name_get(node)
    if root_name in TRANSPARENT_WRAPPER_NAME_SET | {"Optional"} and isinstance(node, ast.Subscript):
        wrapped_node = node.slice.elts[0] if isinstance(node.slice, ast.Tuple) else node.slice
        return _annotation_root_name_get(wrapped_node)
    if root_name == "Union" and isinstance(node, ast.Subscript):
        branch_node_list = list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
        branch_root_name_set = {
            branch_root_name
            for branch_node in branch_node_list
            if not _is_none_annotation_match(branch_node)
            if (branch_root_name := _annotation_root_name_get(branch_node)) is not None
        }
        return next(iter(branch_root_name_set)) if len(branch_root_name_set) == 1 else None
    canonical_name_by_name_map = {
        "Bool": "bool",
        "Datetime": "datetime",
        "Dict": "dict",
        "Int": "int",
        "List": "list",
        "Set": "set",
    }
    return canonical_name_by_name_map.get(root_name, root_name)


def _annotation_visible_name_get(node: ast.AST) -> str | None:
    """Return one direct annotation root token.

    Args:
        node: Candidate annotation expression.

    Returns:
        Visible root name when supported.
    """

    if isinstance(node, ast.Subscript):
        return _annotation_visible_name_get(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _callable_problem_list_get(
    function_node: ast.AST,
    owner_name: str | None,
    relative_path: str,
) -> list[str]:
    """Return callable and typed-child naming problems.

    Args:
        function_node: Candidate function or method.
        owner_name: Optional owning class name.
        relative_path: Repository-relative source path.

    Returns:
        Callable return, parameter, and typed-local problems.
    """

    if not isinstance(function_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
        return []
    if function_node.name.startswith("__") and function_node.name.endswith("__"):
        return []
    display_name = function_node.name if owner_name is None else f"{owner_name}.{function_node.name}"
    problem_list: list[str] = []
    return_root_name = _annotation_root_name_get(function_node.returns)
    inherited_exact_shape = _is_callable_external_exact_shape_match(
        function_node.name,
        owner_name,
        relative_path,
    )
    if not inherited_exact_shape and return_root_name == "bool" and not _is_bool_prefix_match(function_node.name):
        problem_list.append(f"callable {display_name} returning bool must use one canonical boolean prefix")
    if (
        not inherited_exact_shape
        and _is_bool_prefix_match(function_node.name)
        and not function_node.name.startswith("__")
    ):
        if return_root_name != "bool":
            problem_list.append(f"boolean-prefix callable {display_name} must return bool")
    stripped_name = function_node.name.lstrip("_")
    if not inherited_exact_shape and return_root_name == "list" and "_list" not in stripped_name:
        problem_list.append(f"list-returning callable {display_name} must use one _list object phrase")
    if not inherited_exact_shape and return_root_name == "set" and "_set" not in stripped_name:
        problem_list.append(f"set-returning callable {display_name} must use one _set object phrase")
    if (
        not inherited_exact_shape
        and return_root_name == "dict"
        and not (
            _is_callable_dict_object_phrase_match(function_node.name)
            or _is_callable_json_object_boundary_match(function_node.name)
        )
    ):
        problem_list.append(f"dict-returning callable {display_name} must use one value_by_key_map object phrase")
    argument_node_list = [
        *function_node.args.posonlyargs,
        *function_node.args.args,
        *function_node.args.kwonlyargs,
    ]
    if function_node.args.vararg is not None:
        argument_node_list.append(function_node.args.vararg)
    if function_node.args.kwarg is not None:
        argument_node_list.append(function_node.args.kwarg)
    decorator_name_set = {
        name for decorator_node in function_node.decorator_list if (name := call_name_get(decorator_node))
    }
    for argument_node in argument_node_list:
        if argument_node.arg in {"args", "cls", "kwargs", "self"}:
            continue
        if argument_node.arg == "value" and "field_validator" in decorator_name_set:
            continue
        problem_list.extend(_typed_name_problem_list_get(argument_node.arg, argument_node.annotation))
    for node in ast.walk(function_node):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            problem_list.extend(_typed_name_problem_list_get(node.target.id, node.annotation))
    return problem_list


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return naming and collection-carrier findings.

    Args:
        request: Validated checker request.

    Returns:
        Typed-name and callable findings for non-test non-Legacy Python.
    """

    project_root = Path(request["project_root"])
    eligible_relative_path_set = set(
        non_legacy_non_test_python_outside_submodule_relpath_list_get(project_root, scope="all")
    )
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if relative_path not in eligible_relative_path_set or not path.is_file():
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except SyntaxError:
            continue
        for node in module_node.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                for problem in _typed_name_problem_list_get(node.target.id, node.annotation):
                    finding_list.append(
                        ProjectStandardCheckerFinding(line=node.lineno, message=problem, path=relative_path)
                    )
            elif isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                for problem in _callable_problem_list_get(node, None, relative_path):
                    finding_list.append(
                        ProjectStandardCheckerFinding(line=node.lineno, message=problem, path=relative_path)
                    )
            elif isinstance(node, ast.ClassDef):
                for child_node in node.body:
                    if isinstance(child_node, ast.AnnAssign) and isinstance(child_node.target, ast.Name):
                        for problem in _typed_name_problem_list_get(child_node.target.id, child_node.annotation):
                            finding_list.append(
                                ProjectStandardCheckerFinding(
                                    line=child_node.lineno,
                                    message=f"{node.name}: {problem}",
                                    path=relative_path,
                                )
                            )
                    elif isinstance(child_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                        for problem in _callable_problem_list_get(child_node, node.name, relative_path):
                            finding_list.append(
                                ProjectStandardCheckerFinding(
                                    line=child_node.lineno,
                                    message=problem,
                                    path=relative_path,
                                )
                            )
    return finding_list


def _is_bool_prefix_match(name: str) -> bool:
    """Return whether one callable uses an allowed boolean prefix.

    Args:
        name: Candidate callable name.

    Returns:
        Whether the visible name starts with one canonical prefix.
    """

    return name.startswith("__") or name.endswith("__") or name.lstrip("_").startswith(BOOL_PREFIX_TUPLE)


def _is_callable_dict_object_phrase_match(name: str) -> bool:
    """Return whether one callable contains a canonical dict object phrase.

    Args:
        name: Candidate callable name.

    Returns:
        Whether the name contains one complete value-by-key map phrase.
    """

    stripped_name = name.lstrip("_")
    if stripped_name.endswith("_map"):
        return _is_dict_name_match(stripped_name)
    if "_map_" not in stripped_name:
        return False
    return _is_dict_name_match(stripped_name.rsplit("_map_", maxsplit=1)[0] + "_map")


def _is_callable_external_exact_shape_match(name: str, owner_name: str | None, relative_path: str) -> bool:
    """Return whether an inherited or framework contract owns one callable name.

    Args:
        name: Candidate callable name.
        owner_name: Optional owning class name.
        relative_path: Repository-relative source path.

    Returns:
        Whether the callable keeps a framework- or base-owned exact shape.
    """

    if owner_name is not None:
        return name in INHERITED_CALLABLE_NAME_BY_OWNER_MAP.get(owner_name, set())
    return name.startswith("pytest_") and Path(relative_path).name in {"conftest.py", "pytest_plugin.py"}


def _is_callable_json_object_boundary_match(name: str) -> bool:
    """Return whether one callable uses a JSON object boundary phrase.

    Args:
        name: Candidate callable name.

    Returns:
        Whether the callable owns or transports a JSON document or payload.
    """

    stripped_name = name.lstrip("_")
    if _is_json_object_boundary_match(stripped_name):
        return True
    return any(
        stripped_name.endswith(action_suffix)
        and _is_json_object_boundary_match(stripped_name.removesuffix(action_suffix))
        for action_suffix in JSON_OBJECT_BOUNDARY_CALLABLE_ACTION_SUFFIX_TUPLE
    )


def _is_dict_name_match(name: str) -> bool:
    """Return whether one name uses the canonical dict carrier form.

    Args:
        name: Candidate owner-controlled name.

    Returns:
        Whether the name is one complete value-by-key map phrase.
    """

    stripped_name = name.lstrip("_")
    if not stripped_name.endswith("_map"):
        return False
    value_phrase, separator, key_phrase_with_suffix = stripped_name.partition("_by_")
    key_phrase = key_phrase_with_suffix.removesuffix("_map")
    return bool(separator and value_phrase and key_phrase)


def _is_json_object_boundary_match(name: str) -> bool:
    """Return whether one name is a JSON object instead of a local dict carrier.

    Args:
        name: Candidate owner-controlled name.

    Returns:
        Whether the name denotes one boundary document or payload.
    """

    stripped_name = name.lstrip("_")
    return stripped_name in JSON_OBJECT_BOUNDARY_NAME_SET or stripped_name.endswith(JSON_OBJECT_BOUNDARY_SUFFIX_TUPLE)


def _is_none_annotation_match(node: ast.AST) -> bool:
    """Return whether one annotation branch is exactly None.

    Args:
        node: Candidate annotation branch.

    Returns:
        Whether the branch denotes None.
    """

    return (isinstance(node, ast.Constant) and node.value is None) or (
        isinstance(node, ast.Name) and node.id in {"None", "NoneType"}
    )


def _is_temporal_name_match(name: str) -> bool:
    """Return whether one name uses a canonical temporal prefix.

    Args:
        name: Candidate typed name.

    Returns:
        Whether the name denotes one event timestamp.
    """

    stripped_name = name.lstrip("_")
    return stripped_name in {"t_create", "t_update"} or stripped_name.startswith(("t_", "t_create_", "t_update_"))


def _typed_name_problem_list_get(name: str, annotation_node: ast.AST | None) -> list[str]:
    """Return naming/type-shape problems for one typed name.

    Args:
        name: Owner-controlled field, parameter, or local name.
        annotation_node: Declared type annotation.

    Returns:
        Stable suffix and carrier-shape problems.
    """

    if name.startswith("__") and name.endswith("__"):
        return []
    root_name = _annotation_root_name_get(annotation_node)
    annotation_text = ast.unparse(annotation_node) if annotation_node is not None else "untyped"
    problem_list: list[str] = []
    if _is_temporal_name_match(name) and root_name != "datetime":
        problem_list.append(f"temporal name {name} must use datetime or datetime | None, not {annotation_text}")
        return problem_list
    for suffix in NUMERIC_SUFFIX_TUPLE:
        if name.endswith(suffix) and root_name != "int":
            problem_list.append(f"name {name} ending with {suffix} must use int or int | None, not {annotation_text}")
    if name.endswith("_list") and root_name not in LIST_ROOT_NAME_SET:
        problem_list.append(f"name {name} ending with _list must use a list-like type, not {annotation_text}")
    if root_name == "list" and not name.endswith("_list"):
        problem_list.append(f"list-like name {name} must end with _list")
    if name.endswith("_set") and root_name != "set":
        problem_list.append(f"name {name} ending with _set must use set, not {annotation_text}")
    if root_name == "set" and not name.endswith("_set"):
        problem_list.append(f"set name {name} must end with _set")
    if name.endswith("_map") and name.lstrip("_") not in HTTP_HEADER_MAP_NAME_SET and not _is_dict_name_match(name):
        problem_list.append(f"map name {name} must use the form value_by_key_map")
    if _is_dict_name_match(name) and root_name not in DICT_ROOT_NAME_SET:
        problem_list.append(f"map name {name} must use dict or Mapping, not {annotation_text}")
    if (
        root_name == "dict"
        and not _is_dict_name_match(name)
        and not _is_json_object_boundary_match(name)
        and name.lstrip("_") not in HTTP_HEADER_MAP_NAME_SET
    ):
        problem_list.append(f"dict-like name {name} must use the form value_by_key_map")
    if name.lstrip("_") in HTTP_HEADER_MAP_NAME_SET and ast.unparse(annotation_node) not in {
        "dict[str, str]",
        "Mapped[dict[str, str]]",
    }:
        problem_list.append(f"HTTP header map {name} must use dict[str, str]")
    if _is_dict_name_match(name):
        value_phrase, _, key_phrase_with_suffix = name.lstrip("_").partition("_by_")
        key_phrase = key_phrase_with_suffix.removesuffix("_map")
        if value_phrase.endswith("_value"):
            problem_list.append(f"map name {name} must not wrap its mapped object with value")
        if key_phrase.endswith("_key"):
            problem_list.append(f"map name {name} must not wrap its lookup input with key")
    return problem_list


def main() -> int:
    """Run naming and carrier checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
