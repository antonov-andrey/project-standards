#!/usr/bin/env python3
"""Reject repository shell-script artifacts in the declared path scope."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return one finding for every current repository shell script.

    Args:
        request: Validated checker process request.

    Returns:
        Exact shell-script artifact findings.
    """

    return [
        ProjectStandardCheckerFinding(
            message="repository .sh scripts are forbidden; use one intentionally executable Python script",
            path=relative_path,
        )
        for relative_path in request["path_list"]
        if relative_path.endswith(".sh")
    ]


def main() -> int:
    """Run the exact repository shell-script checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
