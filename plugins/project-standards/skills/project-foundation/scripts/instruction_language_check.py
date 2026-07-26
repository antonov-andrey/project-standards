#!/usr/bin/env python3
"""Check instruction assets for one forbidden ambiguous ownership term."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.instruction_asset import instruction_text_relpath_list_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

FORBIDDEN_TERM = "repository-owned"
OWNER_RELATIVE_PATH = "plugins/project-standards/skills/project-foundation/references/writing-and-reporting.md"
OWNER_RULE_MARKER = "The term `repository-owned` is forbidden"


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return forbidden ambiguous ownership-term findings.

    Args:
        request: Validated checker process request.

    Returns:
        Exact instruction paths and lines that use the forbidden term.
    """

    project_root = Path(request["project_root"])
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in instruction_text_relpath_list_get(project_root, request["path_list"]):
        text = (project_root / relative_path).read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_TERM not in line:
                continue
            if relative_path == OWNER_RELATIVE_PATH and OWNER_RULE_MARKER in line:
                continue
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=line_number,
                    message=(
                        f"forbidden instruction term `{FORBIDDEN_TERM}`; "
                        "use `project-local` or explicit path-scoped wording"
                    ),
                    path=relative_path,
                )
            )
    return finding_list


def main() -> int:
    """Run the instruction-language checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
