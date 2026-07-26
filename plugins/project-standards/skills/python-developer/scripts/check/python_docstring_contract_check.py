#!/usr/bin/env python3
"""Check the strict Google-style docstring contract in non-Legacy Python."""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import legacy_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

DOCSTRING_SECTION_NAME_SET = {"Args:", "Raises:", "Returns:"}


def _arg_entry_name_list_get(docstring: str) -> list[str]:
    """Return argument entry names from one Args section.

    Args:
        docstring: Cleaned callable docstring.

    Returns:
        Argument entry names in declaration order.
    """

    line_list = docstring.splitlines()
    section_index_range = _section_index_range_get(line_list, "Args:")
    if section_index_range is None:
        return []
    name_list: list[str] = []
    for line in line_list[section_index_range.start + 1 : section_index_range.stop]:
        match = re.match(r"^\s{4}([*]{0,2}[A-Za-z_][A-Za-z0-9_]*)\s*:", line)
        if match:
            name_list.append(match.group(1).lstrip("*"))
    return name_list


def _argument_name_list_get(function_node: ast.AST, parent_by_node_map: Mapping[ast.AST, ast.AST]) -> list[str]:
    """Return explicit argument names that require documentation.

    Args:
        function_node: Parsed callable node.
        parent_by_node_map: Direct parent lookup for the current module.

    Returns:
        Ordered explicit argument names excluding a real implicit receiver.
    """

    if not isinstance(function_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
        return []
    argument_name_list = [
        *(argument.arg for argument in function_node.args.posonlyargs),
        *(argument.arg for argument in function_node.args.args),
    ]
    if function_node.args.vararg is not None:
        argument_name_list.append(function_node.args.vararg.arg)
    argument_name_list.extend(argument.arg for argument in function_node.args.kwonlyargs)
    if function_node.args.kwarg is not None:
        argument_name_list.append(function_node.args.kwarg.arg)
    receiver_name_set = _method_receiver_name_set_get(function_node, parent_by_node_map)
    return [argument_name for argument_name in argument_name_list if argument_name not in receiver_name_set]


def _docstring_expression_get(node: ast.AST) -> ast.Expr | None:
    """Return one syntax owner's leading docstring expression.

    Args:
        node: Module, class, or callable syntax owner.

    Returns:
        Leading docstring expression when present.
    """

    body_node_list = getattr(node, "body", None)
    if not isinstance(body_node_list, list) or not body_node_list:
        return None
    first_node = body_node_list[0]
    if (
        isinstance(first_node, ast.Expr)
        and isinstance(first_node.value, ast.Constant)
        and isinstance(first_node.value.value, str)
    ):
        return first_node
    return None


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return docstring findings for all current non-Legacy Python.

    Args:
        request: Validated checker request.

    Returns:
        Missing and malformed docstring findings.
    """

    project_root = Path(request["project_root"])
    legacy_relative_path_set = set(legacy_python_relpath_list_get(project_root))
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if not relative_path.endswith(".py") or relative_path in legacy_relative_path_set or not path.is_file():
            continue
        try:
            source = path.read_text(encoding="utf-8")
            module_node = ast.parse(source, filename=relative_path)
        except (OSError, SyntaxError) as error:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    message=f"unable to parse Python for docstring checking: {error}",
                    path=relative_path,
                )
            )
            continue
        source_line_list = source.splitlines()
        parent_by_node_map = {
            child_node: node for node in ast.walk(module_node) for child_node in ast.iter_child_nodes(node)
        }
        module_docstring = ast.get_docstring(module_node, clean=True) or ""
        if not module_docstring.strip():
            finding_list.append(ProjectStandardCheckerFinding(message="missing module docstring", path=relative_path))
        else:
            for problem in [
                *_google_layout_problem_list_get(module_docstring, [], False),
                *_post_docstring_blank_line_problem_list_get(module_node, source_line_list),
            ]:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        message=f"module docstring: {problem}",
                        path=relative_path,
                    )
                )
        for node in ast.walk(module_node):
            if isinstance(node, ast.ClassDef):
                class_docstring = ast.get_docstring(node, clean=True) or ""
                problem_list = (
                    [
                        *_google_layout_problem_list_get(class_docstring, [], False),
                        *_post_docstring_blank_line_problem_list_get(node, source_line_list),
                    ]
                    if class_docstring.strip()
                    else ["missing docstring"]
                )
                for problem in problem_list:
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=node.lineno,
                            message=f"class {node.name}: {problem}",
                            path=relative_path,
                        )
                    )
            elif isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                function_docstring = ast.get_docstring(node, clean=True) or ""
                if not function_docstring.strip():
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=node.lineno,
                            message=f"def {node.name}: missing docstring",
                            path=relative_path,
                        )
                    )
                    continue
                argument_name_list = _argument_name_list_get(node, parent_by_node_map)
                argument_entry_name_list = _arg_entry_name_list_get(function_docstring)
                problem_list = [
                    *(["missing Args section"] if argument_name_list and "Args:" not in function_docstring else []),
                    *[
                        f"missing arg doc for {argument_name!r}"
                        for argument_name in argument_name_list
                        if argument_name not in argument_entry_name_list
                    ],
                    *[
                        f"stale arg doc entry {entry_name!r}"
                        for entry_name in argument_entry_name_list
                        if entry_name not in argument_name_list
                    ],
                ]
                should_have_returns = not _is_none_return_match(node.returns)
                if should_have_returns and "Returns:" not in function_docstring:
                    problem_list.append("missing Returns section")
                problem_list.extend(
                    _google_layout_problem_list_get(
                        function_docstring,
                        argument_name_list,
                        should_have_returns,
                    )
                )
                problem_list.extend(_post_docstring_blank_line_problem_list_get(node, source_line_list))
                for problem in problem_list:
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=node.lineno,
                            message=f"def {node.name}: {problem}",
                            path=relative_path,
                        )
                    )
    return finding_list


def _google_layout_problem_list_get(
    docstring: str,
    argument_name_list: list[str],
    should_have_returns: bool,
) -> list[str]:
    """Return strict Google-style layout problems.

    Args:
        docstring: Cleaned docstring text.
        argument_name_list: Explicit argument names.
        should_have_returns: Whether a Returns section is required.

    Returns:
        Mechanical layout problems.
    """

    if "\n" not in docstring:
        return (
            ["docstring with required sections must be multi-line Google-style"]
            if argument_name_list or should_have_returns or "Raises:" in docstring
            else []
        )
    line_list = docstring.splitlines()
    nonempty_index_list = [index for index, line in enumerate(line_list) if line.strip()]
    if not nonempty_index_list:
        return ["docstring body is empty"]
    problem_list: list[str] = []
    summary_index = nonempty_index_list[0]
    section_index_list = [index for index, line in enumerate(line_list) if line.strip() in DOCSTRING_SECTION_NAME_SET]
    if section_index_list and (summary_index + 1 >= len(line_list) or line_list[summary_index + 1].strip() != ""):
        problem_list.append("missing blank line after summary line")
    for section_index in section_index_list:
        header = line_list[section_index].strip()
        if section_index == 0 or line_list[section_index - 1].strip() != "":
            problem_list.append(f"missing blank line before {header!r} section")
    argument_section_range = _section_index_range_get(line_list, "Args:")
    if argument_section_range is not None:
        argument_line_list = line_list[argument_section_range.start + 1 : argument_section_range.stop]
        if any(line.strip() and not line.startswith("    ") for line in argument_line_list):
            problem_list.append("Args items must be indented by 4 spaces")
        for argument_name in argument_name_list:
            if not any(line.startswith(f"    {argument_name}:") for line in argument_line_list):
                problem_list.append(f"arg entry {argument_name!r} must be indented by 4 spaces")
    return_section_range = _section_index_range_get(line_list, "Returns:")
    if should_have_returns and return_section_range is not None:
        return_line_list = [
            line for line in line_list[return_section_range.start + 1 : return_section_range.stop] if line.strip()
        ]
        if not return_line_list:
            problem_list.append("Returns section must include indented body")
        elif not return_line_list[0].startswith("    "):
            problem_list.append("Returns body must be indented by 4 spaces")
    return problem_list


def _is_none_return_match(node: ast.AST | None) -> bool:
    """Return whether one return annotation represents no returned value.

    Args:
        node: Candidate return annotation.

    Returns:
        Whether the annotation is absent or exactly None.
    """

    return (
        node is None
        or (isinstance(node, ast.Constant) and node.value is None)
        or (isinstance(node, ast.Name) and node.id == "None")
    )


def _method_receiver_name_set_get(
    function_node: ast.AST,
    parent_by_node_map: Mapping[ast.AST, ast.AST],
) -> set[str]:
    """Return the implicit receiver name for one real method.

    Args:
        function_node: Candidate callable node.
        parent_by_node_map: Direct parent lookup for the current module.

    Returns:
        Empty set or one self or cls receiver name.
    """

    if not isinstance(function_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
        return set()
    if not isinstance(parent_by_node_map.get(function_node), ast.ClassDef):
        return set()
    if any(
        isinstance(decorator_node, ast.Name) and decorator_node.id == "staticmethod"
        for decorator_node in function_node.decorator_list
    ):
        return set()
    positional_argument_name_list = [
        *(argument.arg for argument in function_node.args.posonlyargs),
        *(argument.arg for argument in function_node.args.args),
    ]
    return (
        {positional_argument_name_list[0]}
        if positional_argument_name_list and positional_argument_name_list[0] in {"cls", "self"}
        else set()
    )


def _post_docstring_blank_line_problem_list_get(node: ast.AST, source_line_list: Sequence[str]) -> list[str]:
    """Return problems with the exact blank line after one docstring.

    Args:
        node: Module, class, or callable syntax owner.
        source_line_list: Source lines of the current module.

    Returns:
        Missing or extra blank-line problems.
    """

    docstring_expression = _docstring_expression_get(node)
    body_node_list = getattr(node, "body", None)
    if docstring_expression is None or not isinstance(body_node_list, list) or len(body_node_list) < 2:
        return []
    start_line = getattr(docstring_expression, "end_lineno", docstring_expression.lineno)
    end_line = _statement_start_line_get(body_node_list[1])
    if end_line - start_line <= 1:
        return ["missing blank line after docstring block"]
    gap_line_list = source_line_list[start_line : end_line - 1]
    return (
        []
        if len(gap_line_list) == 1 and gap_line_list[0].strip() == ""
        else ["must have exactly one blank line after docstring block"]
    )


def _section_index_range_get(line_list: Sequence[str], header: str) -> range | None:
    """Return one structured-section index range.

    Args:
        line_list: Docstring lines.
        header: Section header to locate.

    Returns:
        Range from header through the exclusive next section.
    """

    start_index = next((index for index, line in enumerate(line_list) if line.strip() == header), None)
    if start_index is None:
        return None
    end_index = len(line_list)
    for index in range(start_index + 1, len(line_list)):
        if line_list[index].strip() in DOCSTRING_SECTION_NAME_SET:
            end_index = index
            break
    return range(start_index, end_index)


def _statement_start_line_get(node: ast.AST) -> int:
    """Return the first source line occupied by one statement.

    Args:
        node: Statement after one docstring.

    Returns:
        Earliest statement or decorator line.
    """

    line = getattr(node, "lineno", 0)
    decorator_node_list = getattr(node, "decorator_list", None)
    return (
        min(line, *(getattr(decorator_node, "lineno", line) for decorator_node in decorator_node_list))
        if isinstance(decorator_node_list, list) and decorator_node_list
        else line
    )


def main() -> int:
    """Run the Python docstring checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
