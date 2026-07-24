#!/usr/bin/env python3
"""Discover Git projects and validate provider-qualified project standards."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess

ALWAYS_REQUIRED_STANDARD_TUPLE = ("project-foundation", "project-instruction-developer")
PLUGIN_NAME = "project-standards"
REQUIRED_HEADING = "## Required Standards"
STANDARD_SKILL_ROOT = Path(__file__).resolve().parents[2]
STRUCTURED_CONFIG_SUFFIX_SET = {".json", ".yaml", ".yml"}


@dataclass(frozen=True)
class ProjectReport:
    """Store one repository classification and validation result."""

    declared_standard_list: list[str]
    git_common_dir: Path
    missing_metadata_list: list[str]
    path: Path
    required_standard_list: list[str]
    unavailable_standard_list: list[str]

    @property
    def missing_standard_list(self) -> list[str]:
        """Return applicable standards absent from project instructions."""

        return sorted(set(self.required_standard_list) - set(self.declared_standard_list))

    @property
    def is_valid(self) -> bool:
        """Return whether this project satisfies the machine-readable contract."""

        return not self.missing_metadata_list and not self.missing_standard_list and not self.unavailable_standard_list

    def payload_get(self) -> dict[str, object]:
        """Return one JSON-compatible project report."""

        return {
            "declared_standard_list": self.declared_standard_list,
            "git_common_dir": str(self.git_common_dir),
            "is_valid": self.is_valid,
            "missing_metadata_list": self.missing_metadata_list,
            "missing_standard_list": self.missing_standard_list,
            "path": str(self.path),
            "required_standard_list": self.required_standard_list,
            "unavailable_standard_list": self.unavailable_standard_list,
        }


def _args_parse() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--check", action="store_true", help="Validate without writes; this is the default.")
    mode_group.add_argument("--write", action="store_true", help="Add missing standard selections and validate again.")
    parser.add_argument(
        "--workspace-root",
        required=True,
        type=Path,
        help="Directory whose immediate children are candidate Git worktrees.",
    )
    return parser.parse_args()


def _available_standard_set_get() -> frozenset[str]:
    """Return capability skill names present in this provider installation."""

    return frozenset(
        path.name for path in STANDARD_SKILL_ROOT.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()
    )


def _declared_standard_list_get(agents_path: Path) -> list[str]:
    """Parse project-standards entries from one Required Standards section.

    Args:
        agents_path: Root project instruction path.

    Returns:
        Sorted unique provider skill names.
    """

    if not agents_path.is_file():
        return []
    text = agents_path.read_text(encoding="utf-8")
    heading_match = re.search(r"(?m)^## Required Standards\s*$", text)
    if heading_match is None:
        return []
    next_heading_match = re.search(r"(?m)^## ", text[heading_match.end() :])
    section_end = len(text) if next_heading_match is None else heading_match.end() + next_heading_match.start()
    section = text[heading_match.end() : section_end]
    return sorted(set(re.findall(r"`project-standards:([a-z0-9-]+)`", section)))


def _git_output_get(project_path: Path, argument_list: list[str]) -> str:
    """Run one read-only Git command.

    Args:
        project_path: Git worktree root.
        argument_list: Arguments passed after ``git``.

    Returns:
        Stripped standard output.
    """

    return subprocess.run(
        ["git", "-C", str(project_path), *argument_list],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


def _missing_metadata_list_get(agents_path: Path) -> list[str]:
    """Return missing root instruction metadata identifiers.

    Args:
        agents_path: Root project instruction path.

    Returns:
        Missing metadata identifiers.
    """

    if not agents_path.is_file():
        return ["AGENTS.md", "Required Standards"]
    text = agents_path.read_text(encoding="utf-8")
    if re.search(r"(?m)^## Required Standards\s*$", text) is None:
        return ["Required Standards"]
    return []


def _project_path_list_get(workspace_root: Path) -> list[Path]:
    """Discover immediate Git worktree children.

    Args:
        workspace_root: Explicit workspace directory.

    Returns:
        Sorted canonical candidate worktree roots.

    Raises:
        ValueError: The supplied workspace root is not a directory.
    """

    if not workspace_root.is_dir():
        raise ValueError(f"Workspace root is not a directory: {workspace_root}")
    return sorted(
        (
            child.resolve()
            for child in workspace_root.iterdir()
            if child.is_dir() and ((child / ".git").is_dir() or (child / ".git").is_file())
        ),
        key=lambda path: path.name,
    )


def _python_signal_set_get(project_path: Path, path_list: list[str]) -> set[str]:
    """Collect structural Python signals without interpreting prose or string fixtures.

    Args:
        project_path: Repository worktree root.
        path_list: Current tracked and untracked non-ignored paths.

    Returns:
        Import, name, attribute, and executable-script signals.
    """

    signal_set: set[str] = set()
    for relative_path in path_list:
        if not relative_path.endswith(".py"):
            continue
        source = (project_path / relative_path).read_text(encoding="utf-8", errors="ignore")
        if source.startswith("#!/usr/bin/env python3"):
            signal_set.add("shebang")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                signal_set.update(f"import:{alias.name}" for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                signal_set.add(f"import:{node.module}")
            elif isinstance(node, ast.Name):
                signal_set.add(f"name:{node.id}")
            elif isinstance(node, ast.Attribute):
                signal_set.add(f"attribute:{node.attr}")
    return signal_set


def _required_standard_list_get(project_path: Path, path_list: list[str]) -> list[str]:
    """Classify applicable standards from current project artifacts.

    Args:
        project_path: Repository worktree root.
        path_list: Current tracked and untracked non-ignored paths.

    Returns:
        Sorted applicable capability skill names.
    """

    required_standard_set = set(ALWAYS_REQUIRED_STANDARD_TUPLE)
    python_path_list = [path for path in path_list if path.endswith(".py")]
    python_signal_set = _python_signal_set_get(project_path, path_list)
    root_agents_path = project_path / "AGENTS.md"
    root_agents_text_lower = (
        root_agents_path.read_text(encoding="utf-8", errors="ignore").lower() if root_agents_path.is_file() else ""
    )
    structured_config_text_lower = "\n".join(
        (project_path / relative_path).read_text(encoding="utf-8", errors="ignore")
        for relative_path in path_list
        if (project_path / relative_path).suffix in STRUCTURED_CONFIG_SUFFIX_SET
        and (project_path / relative_path).is_file()
        and (project_path / relative_path).stat().st_size <= 262_144
    ).lower()

    if python_path_list:
        required_standard_set.add("python-developer")
    if any(path.startswith(("test/", "tests/")) and path.endswith(".py") for path in path_list) or any(
        signal.startswith("import:pytest") for signal in python_signal_set
    ):
        required_standard_set.add("pytest-developer")
    if ".gitmodules" in path_list:
        required_standard_set.add("submodule-developer")
    if any(path == "DESIGN.md" or path.startswith(("design/", "docs/", "doc/", "pattern/")) for path in path_list):
        required_standard_set.add("project-documentation-developer")
    if "`legacy`" in root_agents_text_lower or "legacy python" in root_agents_text_lower:
        required_standard_set.add("legacy-python-maintainer")
    if python_path_list and (
        "shebang" in python_signal_set
        or "import:argparse" in python_signal_set
        or any(signal.startswith("import:config_argparse") for signal in python_signal_set)
    ):
        required_standard_set.add("python-cli-developer")
    if python_path_list and (
        "import:logging" in python_signal_set
        or any(signal.startswith("import:config_logging") for signal in python_signal_set)
    ):
        required_standard_set.add("python-logging-developer")
    if python_path_list and any(
        signal.startswith(("import:retry_runtime", "import:requests_retry", "import:tenacity"))
        for signal in python_signal_set
    ):
        required_standard_set.add("python-retry-developer")
    if python_path_list and any(
        signal.startswith(("import:requests", "import:httpx", "import:aiohttp", "import:urllib3"))
        for signal in python_signal_set
    ):
        required_standard_set.add("http-api-client-developer")
    if python_path_list and any(
        signal.startswith(("import:fastapi", "import:flask", "import:django")) for signal in python_signal_set
    ):
        required_standard_set.add("rest-api-server-developer")
    if python_path_list and (
        any(signal.startswith(("import:config_env", "import:dotenv")) for signal in python_signal_set)
        or ("import:os" in python_signal_set and bool({"attribute:environ", "attribute:getenv"} & python_signal_set))
    ):
        required_standard_set.add("runtime-config-developer")
    if python_path_list and any(
        signal.startswith(("import:sqlalchemy", "import:model_sqlalchemy", "import:config_sqlalchemy"))
        for signal in python_signal_set
    ):
        required_standard_set.add("sqlalchemy-developer")
    if any(path.endswith((".ts", ".tsx")) or path == "tsconfig.json" for path in path_list):
        required_standard_set.add("typescript-developer")
    if any(path.endswith(".tsx") for path in path_list):
        required_standard_set.add("react-ui-developer")
    if any(
        Path(path).name in {"Dockerfile", "compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"}
        for path in path_list
    ):
        required_standard_set.add("docker-compose-developer")
    if "apiversion:" in structured_config_text_lower and any(
        f"kind: {kind}" in structured_config_text_lower
        for kind in ("deployment", "job", "statefulset", "daemonset", "service")
    ):
        required_standard_set.add("kubernetes-developer")
    if (
        "awstemplateformatversion" in structured_config_text_lower
        or "aws::cloudformation" in structured_config_text_lower
    ):
        required_standard_set.add("aws-cloudformation-developer")
    return sorted(required_standard_set)


def _required_standard_write(report: ProjectReport) -> None:
    """Add missing selections while preserving every existing local section.

    Args:
        report: Project report whose missing selections should be added.
    """

    if not report.missing_standard_list:
        return
    agents_path = report.path / "AGENTS.md"
    entry_text = "".join(
        f"- `project-standards:{standard}` applies to the detected project scope.\n"
        for standard in report.missing_standard_list
    )
    if not agents_path.exists():
        agents_path.write_text(f"# Repository Guidelines\n\n{REQUIRED_HEADING}\n\n{entry_text}", encoding="utf-8")
        return
    text = agents_path.read_text(encoding="utf-8")
    heading_match = re.search(r"(?m)^## Required Standards\s*$", text)
    if heading_match is None:
        suffix = "" if text.endswith("\n") else "\n"
        agents_path.write_text(f"{text}{suffix}\n{REQUIRED_HEADING}\n\n{entry_text}", encoding="utf-8")
        return
    section_start = heading_match.end()
    next_heading_match = re.search(r"(?m)^## ", text[section_start:])
    insert_index = len(text) if next_heading_match is None else section_start + next_heading_match.start()
    prefix = text[:insert_index].rstrip()
    suffix = text[insert_index:].lstrip()
    agents_path.write_text(f"{prefix}\n{entry_text}\n{suffix}", encoding="utf-8")


def _workspace_report_get(workspace_root: Path) -> tuple[list[ProjectReport], list[str]]:
    """Build complete workspace validation state.

    Args:
        workspace_root: Explicit workspace directory.

    Returns:
        Project reports and duplicated Git common directories.
    """

    available_standard_set = _available_standard_set_get()
    report_list: list[ProjectReport] = []
    for project_path in _project_path_list_get(workspace_root):
        path_list = _git_output_get(
            project_path,
            ["ls-files", "--cached", "--others", "--exclude-standard"],
        ).splitlines()
        agents_path = project_path / "AGENTS.md"
        declared_standard_list = _declared_standard_list_get(agents_path)
        report_list.append(
            ProjectReport(
                declared_standard_list=declared_standard_list,
                git_common_dir=Path(
                    _git_output_get(project_path, ["rev-parse", "--path-format=absolute", "--git-common-dir"])
                ).resolve(),
                missing_metadata_list=_missing_metadata_list_get(agents_path),
                path=project_path,
                required_standard_list=_required_standard_list_get(project_path, path_list),
                unavailable_standard_list=sorted(set(declared_standard_list) - available_standard_set),
            )
        )
    common_dir_count_by_path_map: dict[Path, int] = {}
    for report in report_list:
        common_dir_count_by_path_map[report.git_common_dir] = (
            common_dir_count_by_path_map.get(report.git_common_dir, 0) + 1
        )
    duplicate_common_dir_list = sorted(str(path) for path, count in common_dir_count_by_path_map.items() if count > 1)
    return report_list, duplicate_common_dir_list


def _workspace_report_print(
    workspace_root: Path,
    report_list: list[ProjectReport],
    duplicate_common_dir_list: list[str],
) -> None:
    """Print deterministic workspace validation JSON.

    Args:
        workspace_root: Explicit workspace directory.
        report_list: Project validation reports.
        duplicate_common_dir_list: Git common directories used by multiple discovered worktrees.
    """

    print(
        json.dumps(
            {
                "duplicate_git_common_dir_list": duplicate_common_dir_list,
                "is_valid": all(report.is_valid for report in report_list) and not duplicate_common_dir_list,
                "project_list": [report.payload_get() for report in report_list],
                "workspace_root": str(workspace_root),
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> int:
    """Validate or update standard selections for one explicit workspace."""

    args = _args_parse()
    workspace_root = args.workspace_root.resolve()
    report_list, duplicate_common_dir_list = _workspace_report_get(workspace_root)
    if args.write:
        if duplicate_common_dir_list:
            raise RuntimeError("Refusing to edit multiple worktrees of one Git common directory")
        for report in report_list:
            _required_standard_write(report)
        report_list, duplicate_common_dir_list = _workspace_report_get(workspace_root)
    _workspace_report_print(workspace_root, report_list, duplicate_common_dir_list)
    return int(not all(report.is_valid for report in report_list) or bool(duplicate_common_dir_list))


if __name__ == "__main__":
    raise SystemExit(main())
