#!/usr/bin/env python3
"""Check canonical Black formatting without mutating the target worktree."""

from __future__ import annotations

from pathlib import Path
import sys

import black

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_scope import legacy_python_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

BLACK_MODE = black.Mode(line_length=120, target_versions={black.TargetVersion.PY314})


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return formatting findings for current non-Legacy Python files.

    Args:
        request: Validated checker request.

    Returns:
        One finding per file that differs from canonical Black output.
    """

    project_root = Path(request["project_root"])
    legacy_relative_path_set = set(legacy_python_relpath_list_get(project_root))
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        path = project_root / relative_path
        if not relative_path.endswith(".py") or relative_path in legacy_relative_path_set or not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        try:
            formatted_source = black.format_file_contents(source, fast=False, mode=BLACK_MODE)
        except black.NothingChanged:
            continue
        except (black.InvalidInput, OSError) as error:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    message=f"Black could not format the file: {error}",
                    path=relative_path,
                )
            )
            continue
        if formatted_source != source:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    message="file differs from Black --target-version py314 --line-length 120",
                    path=relative_path,
                )
            )
    return finding_list


def main() -> int:
    """Run the canonical Black checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
