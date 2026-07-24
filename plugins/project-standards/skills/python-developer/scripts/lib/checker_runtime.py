"""Shared runtime helpers for Python anti-pattern checker scripts."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import subprocess
import sys

TMP_ROOT = Path("/tmp").resolve()


def _git_output_line_list_get(repo_root: Path, argument_list: list[str]) -> list[str]:
    """Run one read-only Git query and return its non-empty output lines.

    Args:
        repo_root: Repository root used by Git.
        argument_list: Arguments passed after ``git``.

    Returns:
        Ordered non-empty output lines.

    Raises:
        ValueError: Git rejects the query.
    """

    result = subprocess.run(
        ["git", "-C", str(repo_root), *argument_list],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Git query failed"
        raise ValueError(message)
    return [line for line in result.stdout.splitlines() if line]


def _repo_root_path_get() -> Path:
    """Resolve the target repository from the checker's current directory.

    Returns:
        Absolute target repository root.

    Raises:
        ValueError: The current directory is not inside a Git worktree.
    """

    line_list = _git_output_line_list_get(Path.cwd(), ["rev-parse", "--show-toplevel"])
    if len(line_list) != 1:
        raise ValueError("Unable to resolve one target Git worktree")
    return Path(line_list[0]).resolve()


ROOT = _repo_root_path_get()


def _is_product_python_path(path: Path) -> bool:
    """Return whether a repository path belongs to product Python scope.

    Args:
        path: Repository-relative candidate path.

    Returns:
        ``True`` for Python files outside support, generated, and task roots.
    """

    if path.suffix != ".py":
        return False
    excluded_root_set = {
        ".agents",
        ".codex",
        ".spec",
        "build",
        "dist",
        "docs",
        "test",
        "tests",
        "tmp",
        "tool",
    }
    return bool(path.parts) and path.parts[0] not in excluded_root_set and "__pycache__" not in path.parts


def _product_python_relpath_list_get() -> list[Path]:
    """Collect current tracked and untracked product Python files.

    Returns:
        Sorted repository-relative Python paths.
    """

    line_list = _git_output_line_list_get(
        ROOT,
        ["ls-files", "--cached", "--others", "--exclude-standard", "--", "*.py"],
    )
    return sorted(
        {
            path
            for line in line_list
            if (path := Path(line)).is_relative_to(Path("."))
            and _is_product_python_path(path)
            and (ROOT / path).is_file()
        },
        key=lambda path: path.as_posix(),
    )


def _changed_python_relpath_list_get() -> list[Path]:
    """Collect changed product Python files from index, worktree, and untracked state.

    Returns:
        Sorted repository-relative changed Python paths.
    """

    changed_path_set: set[Path] = set()
    command_argument_list = [
        ["diff", "--name-only", "--diff-filter=ACMR", "HEAD", "--", "*.py"],
        ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "--", "*.py"],
        ["ls-files", "--others", "--exclude-standard", "--", "*.py"],
    ]
    for argument_list in command_argument_list:
        for line in _git_output_line_list_get(ROOT, argument_list):
            path = Path(line)
            if _is_product_python_path(path) and (ROOT / path).is_file():
                changed_path_set.add(path)
    return sorted(changed_path_set, key=lambda path: path.as_posix())


def _explicit_repo_path_list_get(raw_input_list: list[str]) -> list[Path]:
    """Resolve explicit repository paths into product Python paths.

    Args:
        raw_input_list: Explicit repository file or directory inputs.

    Returns:
        Sorted unique repository-relative Python paths.

    Raises:
        ValueError: An input is outside the target repository or is missing.
    """

    allowed_path_set = set(_product_python_relpath_list_get())
    resolved_path_set: set[Path] = set()
    for raw_input in raw_input_list:
        target = Path(raw_input)
        target = (ROOT / target).resolve() if not target.is_absolute() else target.resolve()
        if not target.exists():
            raise ValueError(f"path does not exist: {raw_input}")
        if not target.is_relative_to(ROOT):
            raise ValueError(f"path is outside the target repository: {raw_input}")
        if target.is_file():
            candidate_path_list = [target]
        else:
            candidate_path_list = sorted(target.rglob("*.py"))
        for candidate_path in candidate_path_list:
            relative_path = candidate_path.resolve().relative_to(ROOT)
            if relative_path in allowed_path_set:
                resolved_path_set.add(relative_path)
    return sorted(resolved_path_set, key=lambda path: path.as_posix())


def _temp_sample_path_list_get(target_list: list[Path]) -> list[Path]:
    """Expand explicit Python sample targets under ``/tmp``.

    Args:
        target_list: Existing resolved targets below the temporary root.

    Returns:
        Sorted unique absolute Python sample paths.
    """

    resolved_path_set: set[Path] = set()
    for target in target_list:
        if target.is_file():
            if target.suffix == ".py":
                resolved_path_set.add(target)
            continue
        resolved_path_set.update(path.resolve() for path in target.rglob("*.py") if path.is_file())
    return sorted(resolved_path_set, key=lambda path: path.as_posix())


def _scope_path_list_explicit_get(raw_input_list: list[str]) -> list[Path]:
    """Resolve explicit repository inputs and isolated test samples.

    Args:
        raw_input_list: Explicit CLI path inputs.

    Returns:
        Sorted unique repository-relative or absolute sample paths.

    Raises:
        ValueError: An input is missing or outside allowed roots.
    """

    repository_input_list: list[str] = []
    temp_target_list: list[Path] = []
    for raw_input in raw_input_list:
        candidate = Path(raw_input)
        candidate = (ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        if not candidate.exists():
            raise ValueError(f"path does not exist: {raw_input}")
        if candidate.is_relative_to(TMP_ROOT):
            temp_target_list.append(candidate)
        else:
            repository_input_list.append(raw_input)
    resolved_path_list = _explicit_repo_path_list_get(repository_input_list) if repository_input_list else []
    resolved_path_list.extend(_temp_sample_path_list_get(temp_target_list))
    return sorted(set(resolved_path_list), key=lambda path: path.as_posix())


def function_arg_list_collect(node: ast.AST) -> list[str]:
    """Collect explicit argument names excluding receivers.

    Args:
        node: Function or method AST node.

    Returns:
        Ordered explicit argument names excluding ``self`` and ``cls``.
    """

    name_list: list[str] = []
    for arg in getattr(node.args, "posonlyargs", []):
        name_list.append(arg.arg)
    for arg in node.args.args:
        name_list.append(arg.arg)
    if node.args.vararg is not None:
        name_list.append(node.args.vararg.arg)
    for arg in node.args.kwonlyargs:
        name_list.append(arg.arg)
    if node.args.kwarg is not None:
        name_list.append(node.args.kwarg.arg)
    return [name for name in name_list if name not in {"self", "cls"}]


def import_root_set(tree: ast.Module) -> set[str]:
    """Collect imported top-level roots from one module.

    Args:
        tree: Parsed module AST.

    Returns:
        Unique imported root names.
    """

    root_set: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root and root != "__future__":
                    root_set.add(root)
            continue
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            root = node.module.split(".", 1)[0]
            if root and root != "__future__":
                root_set.add(root)
    return root_set


def main_project_scope_path_list_resolve(path_list: list[str], scope: str) -> list[Path]:
    """Resolve one target project Python scope.

    Args:
        path_list: Explicit scope inputs from CLI.
        scope: Named scope mode when explicit inputs are absent.

    Returns:
        Sorted Python paths in the resolved scope.
    """

    try:
        if path_list:
            return _scope_path_list_explicit_get(path_list)
        if scope == "changed":
            return _changed_python_relpath_list_get()
        return _product_python_relpath_list_get()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def python_module_parse(path: Path) -> ast.Module:
    """Parse one Python file into an AST.

    Args:
        path: Repository-relative or absolute Python path.

    Returns:
        Parsed module AST.
    """

    source_path = path if path.is_absolute() else ROOT / path
    source = source_path.read_text(encoding="utf-8")
    return ast.parse(source, filename=path.as_posix())


def scope_args_add(parser: argparse.ArgumentParser, *, scope_help: str) -> None:
    """Attach shared target-project scope arguments to one parser.

    Args:
        parser: Target CLI parser.
        scope_help: Help text for explicit path arguments.
    """

    parser.add_argument("paths", nargs="*", help=scope_help)
    parser.add_argument(
        "--scope",
        choices=("all", "changed"),
        default="all",
        help="Scope mode when explicit paths are omitted (default: all).",
    )
