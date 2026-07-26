#!/usr/bin/env python3
"""Check documented Python script commands for inline environment assignments."""

from __future__ import annotations

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.instruction_asset import instruction_text_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

ENVIRONMENT_ASSIGNMENT_COMMAND_PATTERN = r"(?:[A-Z_][A-Z0-9_]*=[^` \t\n]+[ \t]+)+"
SCRIPT_LAUNCH_COMMAND_PATTERN = (
    r"(?:(?:\.?/)?(?:\.codex|plugins|tool)(?:/[^` \t\n]+)+|(?:\.?/)?[^` \t\n]+\.py|python(?:3)?\b|pytest\b)"
)
INLINE_SCRIPT_ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(
    rf"(?m)(?:^|[` \t])(?P<command>{ENVIRONMENT_ASSIGNMENT_COMMAND_PATTERN}{SCRIPT_LAUNCH_COMMAND_PATTERN})"
)


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return documented inline-environment launch findings.

    Args:
        request: Validated checker process request.

    Returns:
        Exact instruction paths and lines with inline assignments.
    """

    project_root = Path(request["project_root"])
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in instruction_text_relpath_list_get(project_root, request["path_list"]):
        text = (project_root / relative_path).read_text(encoding="utf-8")
        for match in INLINE_SCRIPT_ENVIRONMENT_ASSIGNMENT_PATTERN.finditer(text):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=text.count("\n", 0, match.start("command")) + 1,
                    message=(
                        "script command must not use inline environment assignment " f"`{match.group('command')}`"
                    ),
                    path=relative_path,
                )
            )
    return finding_list


def main() -> int:
    """Run the documented script-command checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
