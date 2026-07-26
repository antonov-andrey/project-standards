#!/usr/bin/env python3
"""Check direct-submodule Python code for consumer-specific identifiers."""

from __future__ import annotations

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.git_repository import submodule_name_by_path_map_get
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

ABSOLUTE_USER_PATH_PATTERN = re.compile(r"/home/|/Users/|[A-Za-z]:\\\\")
DATABASE_KEY_PATTERN = re.compile(r"""__database_key__\s*=\s*['"][^'"]+['"]""")


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return direct-submodule portability findings.

    Args:
        request: Validated checker process request.

    Returns:
        Consumer identifier, DB key, and absolute path findings.
    """

    project_root = Path(request["project_root"])
    submodule_relative_path_list = list(submodule_name_by_path_map_get(project_root))
    project_name = project_root.name
    project_identifier_pattern = re.compile(
        rf"\b(?:{re.escape(project_name)}|{re.escape(project_name.replace('-', '_'))})\b"
    )
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        if not relative_path.endswith(".py") or not (project_root / relative_path).is_file():
            continue
        submodule_relative_path = _owning_submodule_relative_path_get(
            relative_path,
            submodule_relative_path_list,
        )
        if submodule_relative_path is None:
            continue
        owner_relative_path = Path(relative_path).relative_to(submodule_relative_path)
        if owner_relative_path.parts[0] in {"test", "tool"}:
            continue
        source = (project_root / relative_path).read_text(encoding="utf-8", errors="ignore")
        for pattern, message in (
            (project_identifier_pattern, "submodule code hardcodes the consuming project identifier"),
            (DATABASE_KEY_PATTERN, "submodule code hardcodes a database key"),
            (ABSOLUTE_USER_PATH_PATTERN, "submodule code hardcodes an absolute user path"),
        ):
            for match in pattern.finditer(source):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=source.count("\n", 0, match.start()) + 1,
                        message=message,
                        path=relative_path,
                    )
                )
    return finding_list


def _owning_submodule_relative_path_get(
    relative_path: str,
    submodule_relative_path_list: list[str],
) -> str | None:
    """Return the direct submodule that owns one repository path.

    Args:
        relative_path: Repository-relative path.
        submodule_relative_path_list: Direct submodule root paths.

    Returns:
        Owning submodule path, otherwise `None`.
    """

    return next(
        (
            submodule_relative_path
            for submodule_relative_path in submodule_relative_path_list
            if relative_path.startswith(f"{submodule_relative_path}/")
        ),
        None,
    )


def main() -> int:
    """Run the direct-submodule portability checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
