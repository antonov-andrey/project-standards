#!/usr/bin/env python3
"""Check that Python signatures use only one type or optional T."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import legacy_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return forbidden signature-union findings.

    Args:
        request: Validated checker request.

    Returns:
        Parameter and return annotation findings.
    """

    project_root = Path(request["project_root"])
    legacy_relative_path_set = set(legacy_python_relpath_list_get(project_root))
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if (
            not relative_path.endswith(".py")
            or relative_path in legacy_relative_path_set
            or "test" in Path(relative_path).parts
            or not path.is_file()
        ):
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except SyntaxError:
            continue
        for function_node in ast.walk(module_node):
            if not isinstance(function_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            argument_node_list = [
                *function_node.args.posonlyargs,
                *function_node.args.args,
                *function_node.args.kwonlyargs,
            ]
            if function_node.args.vararg is not None:
                argument_node_list.append(function_node.args.vararg)
            if function_node.args.kwarg is not None:
                argument_node_list.append(function_node.args.kwarg)
            for argument_node in argument_node_list:
                if argument_node.annotation is not None and _is_forbidden_union_match(argument_node.annotation):
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=function_node.lineno,
                            message=(
                                f"{function_node.name} uses forbidden union in parameter "
                                f"{argument_node.arg}: {ast.unparse(argument_node.annotation)}"
                            ),
                            path=relative_path,
                        )
                    )
            if function_node.returns is not None and _is_forbidden_union_match(function_node.returns):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=function_node.lineno,
                        message=(
                            f"{function_node.name} uses forbidden union in return annotation: "
                            f"{ast.unparse(function_node.returns)}"
                        ),
                        path=relative_path,
                    )
                )
    return finding_list


def _is_forbidden_union_match(node: ast.AST) -> bool:
    """Return whether an annotation contains one non-optional union.

    Args:
        node: Annotation syntax tree.

    Returns:
        Whether any union below the annotation is wider than T plus None.
    """

    for child_node in ast.walk(node):
        is_union = (
            isinstance(child_node, ast.BinOp)
            and isinstance(child_node.op, ast.BitOr)
            or isinstance(child_node, ast.Subscript)
            and isinstance(child_node.value, (ast.Attribute, ast.Name))
            and (child_node.value.attr if isinstance(child_node.value, ast.Attribute) else child_node.value.id)
            in {"Optional", "Union"}
        )
        if is_union and not _is_optional_union_match(child_node):
            return True
    return False


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


def _is_optional_union_match(node: ast.AST) -> bool:
    """Return whether one union is exactly T plus None.

    Args:
        node: Candidate annotation node.

    Returns:
        Whether the node denotes one allowed optional type.
    """

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        branch_node_list = [node.left, node.right]
    elif (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, (ast.Attribute, ast.Name))
        and (node.value.attr if isinstance(node.value, ast.Attribute) else node.value.id) == "Union"
    ):
        branch_node_list = list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
    elif (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, (ast.Attribute, ast.Name))
        and (node.value.attr if isinstance(node.value, ast.Attribute) else node.value.id) == "Optional"
    ):
        return True
    else:
        return False
    return (
        len(branch_node_list) == 2
        and sum(_is_none_annotation_match(branch_node) for branch_node in branch_node_list) == 1
    )


def main() -> int:
    """Run the signature-union checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
