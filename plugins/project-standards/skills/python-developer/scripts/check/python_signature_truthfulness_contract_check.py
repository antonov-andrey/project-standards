#!/usr/bin/env python3
"""Check that Python parameter annotations match the interface actually used."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import non_legacy_non_test_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

ABSTRACT_COLLECTION_ROOT_NAME_SET = {"Collection", "Iterable", "Mapping", "Sequence"}
DICT_READ_METHOD_NAME_SET = {"get", "items", "keys", "values"}
DICT_WRITE_METHOD_NAME_SET = {"clear", "pop", "popitem", "setdefault", "update"}
LIST_MUTATION_METHOD_NAME_SET = {"append", "clear", "extend", "insert", "pop", "remove", "reverse", "sort"}
OS_PATH_OPERATION_NAME_SET = {"mkdir", "open", "remove", "rename", "replace", "rmdir", "stat", "unlink"}
PATH_CONSTRUCTOR_NAME_SET = {"Path", "PurePath", "PurePosixPath", "PureWindowsPath"}
PATH_METHOD_NAME_SET = {
    "absolute",
    "as_posix",
    "exists",
    "glob",
    "is_absolute",
    "is_dir",
    "is_file",
    "iterdir",
    "joinpath",
    "mkdir",
    "open",
    "read_bytes",
    "read_text",
    "relative_to",
    "resolve",
    "rglob",
    "with_name",
    "with_stem",
    "with_suffix",
    "write_bytes",
    "write_text",
}
SET_MUTATION_METHOD_NAME_SET = {
    "add",
    "clear",
    "difference_update",
    "discard",
    "intersection_update",
    "pop",
    "remove",
    "symmetric_difference_update",
    "update",
}


def _annotation_root_name_get(annotation_node: ast.expr) -> str | None:
    """Return one stable root type from a parameter annotation.

    Args:
        annotation_node: Candidate annotation expression.

    Returns:
        Root type name through an optional union when unambiguous.
    """

    if isinstance(annotation_node, ast.Name):
        return annotation_node.id
    if isinstance(annotation_node, ast.Attribute):
        return annotation_node.attr
    if isinstance(annotation_node, ast.Subscript):
        return _annotation_root_name_get(annotation_node.value)
    if not isinstance(annotation_node, ast.BinOp) or not isinstance(annotation_node.op, ast.BitOr):
        return None
    branch_node_list: list[ast.expr] = []
    stack_list: list[ast.expr] = [annotation_node]
    while stack_list:
        node = stack_list.pop()
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            stack_list.extend([node.right, node.left])
        else:
            branch_node_list.append(node)
    root_name_set = {
        root_name
        for branch_node in branch_node_list
        if (root_name := _annotation_root_name_get(branch_node)) not in {None, "None", "NoneType"}
    }
    return next(iter(root_name_set)) if len(root_name_set) == 1 else None


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return parameter-annotation truthfulness findings.

    Args:
        request: Validated checker request.

    Returns:
        Findings across non-Legacy production Python.
    """

    project_root = Path(request["project_root"])
    eligible_relative_path_set = set(non_legacy_non_test_python_relpath_list_get(project_root, scope="all"))
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if relative_path not in eligible_relative_path_set or not path.is_file():
            continue
        try:
            module_node = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        except SyntaxError:
            continue
        for function_node in ast.walk(module_node):
            if not isinstance(function_node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for parameter_node in _parameter_node_list_get(function_node):
                if parameter_node.annotation is None:
                    continue
                annotation_root_name = _annotation_root_name_get(parameter_node.annotation)
                if annotation_root_name is None:
                    continue
                problem = _parameter_problem_get(
                    annotation_root_name,
                    function_node,
                    parameter_node.arg,
                )
                if problem is not None:
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=parameter_node.lineno,
                            message=(f"parameter {parameter_node.arg} annotated as {annotation_root_name} {problem}"),
                            path=relative_path,
                        )
                    )
    return finding_list


def _parameter_node_list_get(function_node: ast.stmt) -> list[ast.arg]:
    """Return explicit non-receiver parameters for one callable.

    Args:
        function_node: Callable declaration.

    Returns:
        Typed parameter nodes excluding conventional receiver and packing names.
    """

    parameter_node_list = [
        *function_node.args.posonlyargs,
        *function_node.args.args,
        *function_node.args.kwonlyargs,
    ]
    if function_node.args.vararg is not None:
        parameter_node_list.append(function_node.args.vararg)
    if function_node.args.kwarg is not None:
        parameter_node_list.append(function_node.args.kwarg)
    return [
        parameter_node
        for parameter_node in parameter_node_list
        if parameter_node.arg not in {"args", "cls", "kwargs", "self"}
    ]


def _parameter_problem_get(
    annotation_root_name: str,
    function_node: ast.stmt,
    parameter_name: str,
) -> str | None:
    """Return the first truthful-signature problem for one parameter.

    Args:
        annotation_root_name: Declared annotation root.
        function_node: Owning callable.
        parameter_name: Parameter under analysis.

    Returns:
        Concrete mismatch text when one contract is violated.
    """

    visitor = ParameterUsageVisitor(function_node, parameter_name)
    visitor.visit(function_node)
    if annotation_root_name in ABSTRACT_COLLECTION_ROOT_NAME_SET:
        return visitor.abstract_problem_get(annotation_root_name)
    if annotation_root_name in {"Any", "object"}:
        return visitor.broad_problem_get()
    if annotation_root_name in {"dict", "list", "str"}:
        return visitor.concrete_problem_get(annotation_root_name)
    return None


def main() -> int:
    """Run signature-truthfulness checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


class ParameterUsageVisitor(ast.NodeVisitor):
    """Analyze operations performed directly on one callable parameter."""

    def __init__(self, function_node: ast.stmt, parameter_name: str) -> None:
        """Initialize one parameter-bound usage analysis.

        Args:
            function_node: Callable declaration that owns the parameter.
            parameter_name: Parameter name to inspect.
        """

        self._contains_used = False
        self._dict_read_used = False
        self._dict_write_used = False
        self._function_node = function_node
        self._iterable_used = False
        self._len_used = False
        self._list_mutation_used = False
        self._parameter_name = parameter_name
        self._path_constructor_used = False
        self._path_operation_used = False
        self._set_mutation_used = False
        self._subscript_used = False
        self._type_branch_used = False

    def abstract_problem_get(self, annotation_root_name: str) -> str | None:
        """Return an abstract-interface mismatch after visiting the callable.

        Args:
            annotation_root_name: Declared abstract collection root.

        Returns:
            Concrete mismatch text when used operations exceed the interface.
        """

        if annotation_root_name == "Iterable" and (
            self._contains_used or self._dict_read_used or self._len_used or self._subscript_used
        ):
            return "uses operations outside iteration-only contract"
        if annotation_root_name == "Collection" and (self._dict_read_used or self._subscript_used):
            return "uses operations outside membership/length contract"
        if annotation_root_name == "Sequence" and (
            self._dict_read_used or self._dict_write_used or self._list_mutation_used or self._set_mutation_used
        ):
            return "uses operations outside ordered read-only contract"
        if annotation_root_name == "Mapping" and (
            self._dict_write_used or self._list_mutation_used or self._set_mutation_used
        ):
            return "uses operations outside read-only key/value contract"
        return None

    def broad_problem_get(self) -> str | None:
        """Return a shape-specific use hidden behind Any or object.

        Returns:
            Concrete path or collection mismatch text.
        """

        if self._type_branch_used:
            return None
        if self._path_constructor_used or self._path_operation_used:
            return "uses one path-specific runtime contract"
        if self._contains_used or self._iterable_used or self._len_used or self._subscript_used:
            return "uses one collection-specific runtime contract"
        return None

    def concrete_problem_get(self, annotation_root_name: str) -> str | None:
        """Return an unnecessarily concrete collection mismatch.

        Args:
            annotation_root_name: Declared concrete collection root.

        Returns:
            Narrower sufficient interface text when determinable.
        """

        if (
            annotation_root_name == "list"
            and self._subscript_used
            and not (self._dict_write_used or self._list_mutation_used or self._set_mutation_used)
        ):
            return "uses only ordered read-only sequence operations"
        if (
            annotation_root_name == "dict"
            and self._dict_read_used
            and not (
                self._dict_write_used or self._list_mutation_used or self._set_mutation_used or self._subscript_used
            )
        ):
            return "uses only read-only mapping operations"
        if annotation_root_name == "str" and self._path_operation_used:
            return "uses path operations before one boundary normalization to Path"
        return None

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        """Record direct async iteration without entering nested scopes.

        Args:
            node: Candidate async-for statement.
        """

        if self._is_parameter_name_match(node.iter):
            self._iterable_used = True
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit only the analyzed async function, not nested callables.

        Args:
            node: Candidate async function.
        """

        if node is self._function_node:
            self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Record pathlib-style division.

        Args:
            node: Candidate binary expression.
        """

        if isinstance(node.op, ast.Div) and self._is_parameter_name_match(node.left):
            self._path_operation_used = True
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Record collection methods, path calls, and type branches.

        Args:
            node: Candidate call expression.
        """

        function_node = node.func
        if isinstance(function_node, ast.Name):
            if function_node.id == "len" and len(node.args) == 1 and self._is_parameter_name_match(node.args[0]):
                self._len_used = True
            if function_node.id == "open" and node.args and self._is_parameter_name_match(node.args[0]):
                self._path_operation_used = True
            if function_node.id == "isinstance" and node.args and self._is_parameter_name_match(node.args[0]):
                self._type_branch_used = True
            if function_node.id in PATH_CONSTRUCTOR_NAME_SET and any(
                self._is_parameter_name_match(argument_node) for argument_node in node.args
            ):
                self._path_constructor_used = True
        elif isinstance(function_node, ast.Attribute):
            if self._is_parameter_name_match(function_node.value):
                if function_node.attr in DICT_READ_METHOD_NAME_SET:
                    self._dict_read_used = True
                if function_node.attr in DICT_WRITE_METHOD_NAME_SET:
                    self._dict_write_used = True
                if function_node.attr in LIST_MUTATION_METHOD_NAME_SET:
                    self._list_mutation_used = True
                if function_node.attr in PATH_METHOD_NAME_SET:
                    self._path_operation_used = True
                if function_node.attr in SET_MUTATION_METHOD_NAME_SET:
                    self._set_mutation_used = True
            elif (
                isinstance(function_node.value, ast.Attribute)
                and isinstance(function_node.value.value, ast.Name)
                and function_node.value.value.id == "os"
                and function_node.value.attr == "path"
                and any(self._is_parameter_name_match(argument_node) for argument_node in node.args)
            ):
                self._path_operation_used = True
            elif (
                isinstance(function_node.value, ast.Name)
                and function_node.value.id == "os"
                and function_node.attr in OS_PATH_OPERATION_NAME_SET
                and any(self._is_parameter_name_match(argument_node) for argument_node in node.args)
            ):
                self._path_operation_used = True
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Do not attribute nested-class operations to the callable.

        Args:
            node: Candidate nested class.
        """

    def visit_Compare(self, node: ast.Compare) -> None:
        """Record membership operations where the parameter is the container.

        Args:
            node: Candidate comparison.
        """

        if any(isinstance(operator_node, (ast.In, ast.NotIn)) for operator_node in node.ops) and any(
            self._is_parameter_name_match(comparator_node) for comparator_node in node.comparators
        ):
            self._contains_used = True
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit only the analyzed function, not nested callables.

        Args:
            node: Candidate function.
        """

        if node is self._function_node:
            self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Record direct iteration.

        Args:
            node: Candidate for statement.
        """

        if self._is_parameter_name_match(node.iter):
            self._iterable_used = True
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Record indexing and indexed mutation.

        Args:
            node: Candidate subscript expression.
        """

        if self._is_parameter_name_match(node.value):
            self._subscript_used = True
            if isinstance(node.ctx, (ast.Del, ast.Store)):
                self._dict_write_used = True
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        """Record comprehension iteration.

        Args:
            node: Candidate comprehension clause.
        """

        if self._is_parameter_name_match(node.iter):
            self._iterable_used = True
        self.generic_visit(node)

    def _is_parameter_name_match(self, node: ast.AST) -> bool:
        """Return whether one load expression is the analyzed parameter.

        Args:
            node: Candidate syntax node.

        Returns:
            Whether the node loads the target parameter.
        """

        return isinstance(node, ast.Name) and node.id == self._parameter_name and isinstance(node.ctx, ast.Load)


if __name__ == "__main__":
    raise SystemExit(main())
