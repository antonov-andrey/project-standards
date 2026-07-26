#!/usr/bin/env python3
"""Check Python script artifacts, direct help, and repository shell-script bans."""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import stat
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.git_repository import submodule_name_by_path_map_get
from project_standards.project_standard_model import (
    ProjectStandardCheckerFinding,
    ProjectStandardRequest,
    ProjectStandardScriptLaunchConfig,
)

SCRIPT_HELP_LAUNCH_TIMEOUT_SECONDS = 15
SCRIPT_HELP_OPTION_SET = {"--help", "-h"}
SCRIPT_SHEBANG = "#!/usr/bin/env python3"


def _call_name_get(node: ast.Call) -> str:
    """Return one statically visible call target name.

    Args:
        node: Candidate call node.

    Returns:
        Attribute or name call target, otherwise an empty string.
    """

    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _contain_help_option(node: ast.AST) -> bool:
    """Return whether one AST subtree contains a help-option literal.

    Args:
        node: Candidate syntax subtree.

    Returns:
        Whether `--help` or `-h` occurs below the node.
    """

    return any(isinstance(child, ast.Constant) and child.value in SCRIPT_HELP_OPTION_SET for child in ast.walk(node))


def _external_repository_import_name_list_get(
    project_root: Path,
    script_path: Path,
    submodule_root: Path,
    relative_path_list: list[str],
) -> list[str]:
    """Return imports that escape one direct submodule into consumer code.

    Args:
        project_root: Exact consumer repository root.
        script_path: Direct-submodule script path.
        submodule_root: Owning direct-submodule root.
        relative_path_list: Complete manifest-selected current paths.

    Returns:
        Sorted top-level import names owned only outside the submodule.
    """

    submodule_relative_path = submodule_root.relative_to(project_root).as_posix()
    repository_root_name_set = _python_top_level_root_name_set_get(relative_path_list)
    submodule_root_name_set = _python_top_level_root_name_set_get(
        [
            relative_path.removeprefix(f"{submodule_relative_path}/")
            for relative_path in relative_path_list
            if relative_path.startswith(f"{submodule_relative_path}/")
        ]
    )
    disallowed_root_name_set = repository_root_name_set - submodule_root_name_set
    standard_root_name_set = set(sys.stdlib_module_names) | {"__future__"}
    violation_name_set: set[str] = set()
    syntax_tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=script_path.as_posix())
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".", maxsplit=1)[0]
                if root_name not in standard_root_name_set and root_name in disallowed_root_name_set:
                    violation_name_set.add(root_name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root_name = node.module.split(".", maxsplit=1)[0]
            if root_name not in standard_root_name_set and root_name in disallowed_root_name_set:
                violation_name_set.add(root_name)
    return sorted(violation_name_set)


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return all Python CLI and executable-artifact findings.

    Args:
        request: Validated checker process request.

    Returns:
        Static artifact and direct-launch findings.
    """

    project_root = Path(request["project_root"])
    relative_path_list = request["path_list"]
    submodule_relative_path_list = list(submodule_name_by_path_map_get(project_root))
    finding_list = [
        ProjectStandardCheckerFinding(
            line=1,
            message="repository shell scripts are forbidden",
            path=relative_path,
        )
        for relative_path in relative_path_list
        if relative_path.endswith(".sh")
        and (project_root / relative_path).is_file()
        and not _is_under_root_list(relative_path, submodule_relative_path_list)
    ]
    launch_config_list: list[ProjectStandardScriptLaunchConfig] = []
    for relative_path in relative_path_list:
        path = project_root / relative_path
        if not relative_path.endswith(".py") or not path.is_file():
            continue
        submodule_relative_path = _owning_root_get(relative_path, submodule_relative_path_list)
        if submodule_relative_path is None:
            if not _have_main_guard(path):
                continue
            if not _is_root_script_path(relative_path, project_root):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=_main_guard_line_get(path),
                        message="unexpected __main__ guard outside an intentionally executable path",
                        path=relative_path,
                    )
                )
                continue
            finding_list.extend(_script_static_finding_list_get(path, relative_path))
            launch_config_list.append(
                ProjectStandardScriptLaunchConfig(
                    command_path=_launch_relative_path_get(relative_path),
                    project_root=project_root,
                    working_root=project_root,
                )
            )
            continue
        if not _have_main_guard(path):
            continue
        finding_list.extend(_script_static_finding_list_get(path, relative_path))
        submodule_root = project_root / submodule_relative_path
        try:
            import_name_list = _external_repository_import_name_list_get(
                project_root,
                path,
                submodule_root,
                relative_path_list,
            )
        except SyntaxError:
            import_name_list = []
        if import_name_list:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    message=f"script imports consumer code outside its owning submodule: {', '.join(import_name_list)}",
                    path=relative_path,
                )
            )
        launch_config_list.append(
            ProjectStandardScriptLaunchConfig(
                command_path=relative_path,
                project_root=project_root,
                working_root=project_root,
            )
        )
        submodule_script_relative_path = Path(relative_path).relative_to(submodule_relative_path).as_posix()
        launch_config_list.append(
            ProjectStandardScriptLaunchConfig(
                command_path=_launch_relative_path_get(submodule_script_relative_path),
                project_root=project_root,
                working_root=submodule_root,
            )
        )
    with ThreadPoolExecutor(max_workers=8) as executor:
        launch_finding_list = list(executor.map(_script_launch_finding_get, launch_config_list))
    finding_list.extend(finding for finding in launch_finding_list if finding is not None)
    return finding_list


def _have_main_guard(path: Path) -> bool:
    """Return whether one Python file has a top-level main guard.

    Args:
        path: Python source path.

    Returns:
        Whether a canonical or reversed `__main__` comparison exists.
    """

    try:
        syntax_tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    except SyntaxError:
        return False
    return any(_is_main_guard(node) for node in syntax_tree.body)


def _is_argument_parser_add_help_disabled(node: ast.Call) -> bool:
    """Return whether one parser constructor disables standard help.

    Args:
        node: Candidate call node.

    Returns:
        Whether the call is `ArgumentParser(add_help=False)`.
    """

    return _call_name_get(node) == "ArgumentParser" and any(
        keyword.arg == "add_help" and isinstance(keyword.value, ast.Constant) and keyword.value.value is False
        for keyword in node.keywords
    )


def _is_main_guard(node: ast.stmt) -> bool:
    """Return whether one top-level statement is a main guard.

    Args:
        node: Candidate top-level statement.

    Returns:
        Whether the statement compares `__name__` with `"__main__"`.
    """

    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    comparison = node.test
    if len(comparison.ops) != 1 or not isinstance(comparison.ops[0], ast.Eq) or len(comparison.comparators) != 1:
        return False
    left = comparison.left
    right = comparison.comparators[0]
    return (
        isinstance(left, ast.Name)
        and left.id == "__name__"
        and isinstance(right, ast.Constant)
        and right.value == "__main__"
    ) or (
        isinstance(right, ast.Name)
        and right.id == "__name__"
        and isinstance(left, ast.Constant)
        and left.value == "__main__"
    )


def _is_manual_help_argument(node: ast.Call) -> bool:
    """Return whether one parser call declares a manual help option.

    Args:
        node: Candidate call node.

    Returns:
        Whether `add_argument` receives `--help` or `-h`.
    """

    return _call_name_get(node) == "add_argument" and any(
        isinstance(argument, ast.Constant) and argument.value in SCRIPT_HELP_OPTION_SET for argument in node.args
    )


def _is_root_script_path(relative_path: str, project_root: Path) -> bool:
    """Return whether one root-owned path is an intentional script location.

    Args:
        relative_path: Repository-relative Python path.
        project_root: Exact repository root.

    Returns:
        Whether the path is root-level, tool-owned, agent-owned, or Skill-owned.
    """

    part_tuple = Path(relative_path).parts
    if len(part_tuple) == 1 or part_tuple[0] == "tool":
        return True
    if len(part_tuple) >= 5 and part_tuple[:2] == (".codex", "agents") and part_tuple[-2] == "tool":
        return True
    if (
        len(part_tuple) >= 5
        and part_tuple[:2] == (".codex", "skills")
        and part_tuple[2] != ".system"
        and part_tuple[-2] == "tool"
    ):
        return True
    if len(part_tuple) >= 6 and part_tuple[:3] == (".codex", "skills", ".system") and part_tuple[-2] == "scripts":
        return True
    path = project_root / relative_path
    for parent in path.parents:
        if parent == project_root:
            break
        if parent.name == "scripts" and (parent.parent / "SKILL.md").is_file():
            return True
    return False


def _is_under_root_list(relative_path: str, root_relative_path_list: list[str]) -> bool:
    """Return whether one path belongs to any declared direct root.

    Args:
        relative_path: Repository-relative path.
        root_relative_path_list: Direct root paths.

    Returns:
        Whether the path equals or descends from one root.
    """

    return any(
        relative_path == root_relative_path or relative_path.startswith(f"{root_relative_path}/")
        for root_relative_path in root_relative_path_list
    )


def _launch_environment_value_by_name_map_get(project_root: Path, working_root: Path) -> dict[str, str]:
    """Return one minimal direct-script launch environment.

    Args:
        project_root: Exact consumer repository root.
        working_root: Direct command working directory.

    Returns:
        Environment with the project virtualenv and working root on `PATH`.
    """

    environment_value_by_name_map = {"HOME": os.environ.get("HOME", "/tmp")}
    for name in ("LANG", "LC_ALL", "TZ"):
        if name in os.environ:
            environment_value_by_name_map[name] = os.environ[name]
    path_item_list = [
        str(Path(sys.executable).parent),
        str(project_root / ".venv" / "bin"),
        str(working_root),
        os.defpath,
    ]
    existing_path = os.environ.get("PATH", "")
    if existing_path:
        path_item_list.append(existing_path)
    environment_value_by_name_map["PATH"] = ":".join(path_item_list)
    return environment_value_by_name_map


def _launch_relative_path_get(relative_path: str) -> str:
    """Return one direct command path relative to its owning root.

    Args:
        relative_path: Owner-relative script path.

    Returns:
        Direct executable path with a root-file prefix when needed.
    """

    return relative_path if "/" in relative_path else f"./{relative_path}"


def _main_guard_line_get(path: Path) -> int:
    """Return the first top-level main-guard line.

    Args:
        path: Python source path.

    Returns:
        Main-guard line, or line one when parsing fails.
    """

    try:
        syntax_tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    except SyntaxError:
        return 1
    return next((node.lineno for node in syntax_tree.body if _is_main_guard(node)), 1)


def _owning_root_get(relative_path: str, root_relative_path_list: list[str]) -> str | None:
    """Return the direct root that owns one path.

    Args:
        relative_path: Repository-relative path.
        root_relative_path_list: Candidate direct roots.

    Returns:
        Owning root path, otherwise `None`.
    """

    return next(
        (
            root_relative_path
            for root_relative_path in root_relative_path_list
            if relative_path == root_relative_path or relative_path.startswith(f"{root_relative_path}/")
        ),
        None,
    )


def _python_top_level_root_name_set_get(relative_path_list: list[str]) -> set[str]:
    """Return top-level Python package or module roots for one path set.

    Args:
        relative_path_list: Owner-relative current paths.

    Returns:
        Top-level names backed by Python files.
    """

    root_name_set: set[str] = set()
    for relative_path in relative_path_list:
        if not relative_path.endswith(".py"):
            continue
        path = Path(relative_path)
        root_name_set.add(path.stem if len(path.parts) == 1 else path.parts[0])
    return root_name_set


def _script_help_shortcut_finding_list_get(path: Path, relative_path: str) -> list[ProjectStandardCheckerFinding]:
    """Return static help-path bypass findings for one script.

    Args:
        path: Python script path.
        relative_path: Repository-relative diagnostic path.

    Returns:
        Help shortcut, disabled help, and manual help findings.
    """

    try:
        syntax_tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    except SyntaxError as error:
        return [
            ProjectStandardCheckerFinding(
                line=error.lineno or 1,
                message="failed to parse Python source for help shortcut check",
                path=relative_path,
            )
        ]
    finding_list: list[ProjectStandardCheckerFinding] = []
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.If) and _contain_help_option(node.test):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message="--help must use the standard parser path, not an explicit help shortcut",
                    path=relative_path,
                )
            )
        elif isinstance(node, ast.Call) and _is_argument_parser_add_help_disabled(node):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message="--help must use the standard parser path, not ArgumentParser(add_help=False)",
                    path=relative_path,
                )
            )
        elif isinstance(node, ast.Call) and _is_manual_help_argument(node):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=node.lineno,
                    message="--help must use the standard parser path, not a manual help argument",
                    path=relative_path,
                )
            )
    return finding_list


def _script_launch_finding_get(
    launch_config: ProjectStandardScriptLaunchConfig,
) -> ProjectStandardCheckerFinding | None:
    """Return one direct-help launch finding.

    Args:
        launch_config: Named working root, command path, and consumer root.

    Returns:
        Launch failure or timeout finding, otherwise `None`.
    """

    command_path = launch_config["command_path"]
    project_root = launch_config["project_root"]
    working_root = launch_config["working_root"]
    diagnostic_path = (working_root / command_path).resolve().relative_to(project_root).as_posix()
    try:
        result = subprocess.run(
            [command_path, "--help"],
            capture_output=True,
            check=False,
            cwd=working_root,
            env=_launch_environment_value_by_name_map_get(project_root, working_root),
            text=True,
            timeout=SCRIPT_HELP_LAUNCH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return ProjectStandardCheckerFinding(
            message=f"direct launch with --help failed: {error}",
            path=diagnostic_path,
        )
    if result.returncode == 0:
        return None
    output = result.stderr.strip() or result.stdout.strip() or "no output"
    return ProjectStandardCheckerFinding(
        message=f"direct launch with --help failed: {output.replace(chr(10), ' ')[:240]}",
        path=diagnostic_path,
    )


def _script_static_finding_list_get(path: Path, relative_path: str) -> list[ProjectStandardCheckerFinding]:
    """Return shebang, mode, and static help-path findings for one script.

    Args:
        path: Python script path.
        relative_path: Repository-relative diagnostic path.

    Returns:
        Static executable-artifact findings.
    """

    finding_list = _script_help_shortcut_finding_list_get(path, relative_path)
    line_list = path.read_text(encoding="utf-8").splitlines()
    if not line_list or line_list[0] != SCRIPT_SHEBANG:
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=1,
                message=f"missing required shebang {SCRIPT_SHEBANG!r}",
                path=relative_path,
            )
        )
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != 0o755:
        finding_list.append(
            ProjectStandardCheckerFinding(
                message=f"expected executable mode 755, found {mode:o}",
                path=relative_path,
            )
        )
    return finding_list


def main() -> int:
    """Run the Python script contract checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
