#!/usr/bin/env python3
"""Check maintained Markdown file targets and an existing script catalog."""

from __future__ import annotations

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

EXTERNAL_TARGET_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")
INLINE_LINK_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)|\[[^\]]+\]\(([^)]+)\)")


def _catalog_finding_list_get(project_root: Path) -> list[ProjectStandardCheckerFinding]:
    """Return findings for one existing root script catalog.

    Args:
        project_root: Exact target repository root.

    Returns:
        Missing, extra, duplicate, or unordered catalog findings.
    """

    catalog_path = project_root / "docs" / "script_catalog.md"
    if not catalog_path.is_file():
        return []
    text = catalog_path.read_text(encoding="utf-8")
    section_marker = "\n## Каталог Скриптов\n"
    if section_marker not in text:
        return [
            ProjectStandardCheckerFinding(
                message="script catalog must contain section `## Каталог Скриптов`",
                path="docs/script_catalog.md",
            )
        ]
    actual_entry_list = re.findall(
        r"^- `([^`]+\.py)` - ",
        text.split(section_marker, maxsplit=1)[1],
        flags=re.MULTILINE,
    )
    expected_entry_list = sorted(
        path.name
        for path in project_root.glob("*.py")
        if path.name != "conftest.py" and (project_root / "script" / path.stem / "entrypoint.py").is_file()
    )
    finding_list: list[ProjectStandardCheckerFinding] = []
    if actual_entry_list != sorted(actual_entry_list):
        finding_list.append(
            ProjectStandardCheckerFinding(
                message="script catalog entries must be alphabetically sorted",
                path="docs/script_catalog.md",
            )
        )
    if actual_entry_list != expected_entry_list:
        finding_list.append(
            ProjectStandardCheckerFinding(
                message=(
                    "script catalog entries must exactly cover Product root entrypoints: "
                    f"expected {expected_entry_list!r}, found {actual_entry_list!r}"
                ),
                path="docs/script_catalog.md",
            )
        )
    return finding_list


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return all documentation contract findings for one target repository.

    Args:
        request: Validated checker process request.

    Returns:
        Markdown target and script-catalog findings.
    """

    project_root = Path(request["project_root"])
    return _catalog_finding_list_get(project_root) + _markdown_finding_list_get(
        project_root,
        request["path_list"],
    )


def _link_target_get(document_path: Path, target: str) -> Path:
    """Resolve one normalized target against its Markdown document.

    Args:
        document_path: Markdown document path.
        target: Normalized local target.

    Returns:
        Absolute resolved filesystem target.
    """

    target_path = Path(target)
    return target_path.resolve() if target_path.is_absolute() else (document_path.parent / target_path).resolve()


def _markdown_finding_list_get(
    project_root: Path,
    relative_path_list: list[str],
) -> list[ProjectStandardCheckerFinding]:
    """Return broken repository-local Markdown file targets.

    Args:
        project_root: Exact target repository root.
        relative_path_list: Manifest-selected current paths.

    Returns:
        Broken or escaping file-target findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    markdown_relative_path_list = sorted(
        relative_path
        for relative_path in relative_path_list
        if relative_path.endswith(".md") and (project_root / relative_path).is_file()
    )
    for relative_path in markdown_relative_path_list:
        document_path = project_root / relative_path
        inside_fence = False
        for line_number, raw_line in enumerate(document_path.read_text(encoding="utf-8").splitlines(), start=1):
            if FENCE_PATTERN.match(raw_line):
                inside_fence = not inside_fence
                continue
            if inside_fence:
                continue
            for match in INLINE_LINK_PATTERN.finditer(raw_line):
                target = _target_normalize(match.group(1) or match.group(2) or "")
                if target is None:
                    continue
                resolved_target = _link_target_get(document_path, target)
                if not resolved_target.is_relative_to(project_root) or not resolved_target.exists():
                    finding_list.append(
                        ProjectStandardCheckerFinding(
                            line=line_number,
                            message=f"broken repository-local Markdown target: {target!r}",
                            path=relative_path,
                        )
                    )
    return finding_list


def _target_normalize(raw_target: str) -> str | None:
    """Normalize one Markdown target or classify it as non-local.

    Args:
        raw_target: Raw target text captured from Markdown.

    Returns:
        Local file target without query or fragment, otherwise `None`.
    """

    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if not target or target.startswith(("#", "~/.codex/skills/")) or EXTERNAL_TARGET_PATTERN.match(target):
        return None
    target = target.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0].strip()
    return target or None


def main() -> int:
    """Run the documentation checker process.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
