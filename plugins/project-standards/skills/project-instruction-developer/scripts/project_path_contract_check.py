#!/usr/bin/env python3
"""Check Main project Python placement against declared directory-map paths."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_instruction import (
    key_directory_map_path_template_list_get,
    match_path_template,
    match_path_template_directory,
)
from project_standards.project_scope import main_project_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

BROAD_MAIN_PROJECT_ROOT_NAME_SET = {"backend", "lib", "plugins", "script"}


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return undeclared Main project Python path findings.

    Args:
        request: Validated checker process request.

    Returns:
        Paths outside the current canonical Key Directory Map.
    """

    project_root = Path(request["project_root"])
    path_template_list = key_directory_map_path_template_list_get(project_root / "AGENTS.md")
    broad_path_template_list = [
        path_template
        for path_template in path_template_list
        if path_template.endswith("/") and path_template.split("/", maxsplit=1)[0] in BROAD_MAIN_PROJECT_ROOT_NAME_SET
    ]
    requested_path_set = set(request["path_list"])
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in main_project_python_relpath_list_get(project_root, scope="all"):
        if relative_path not in requested_path_set:
            continue
        if relative_path.endswith("/__init__.py") and any(
            relative_path == f"{path_template.split('/', maxsplit=1)[0]}/__init__.py"
            for path_template in broad_path_template_list
        ):
            continue
        if any(
            match_path_template_directory(relative_path, path_template) for path_template in broad_path_template_list
        ):
            continue
        if any(match_path_template(relative_path, path_template) for path_template in path_template_list):
            continue
        finding_list.append(
            ProjectStandardCheckerFinding(
                line=1,
                message="Main project Python path is not declared by the Key Directory Map",
                path=relative_path,
            )
        )
    return finding_list


def main() -> int:
    """Run project path-declaration checking.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
