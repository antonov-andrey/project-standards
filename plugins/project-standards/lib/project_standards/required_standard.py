"""Parse selected project standards from canonical repository instructions."""

from __future__ import annotations

from pathlib import Path
import re

REQUIRED_STANDARD_HEADING = "## Required Standards"


def required_standard_name_list_get(agents_path: Path) -> list[str]:
    """Return selected project-standard capability names.

    Args:
        agents_path: Root repository instruction file.

    Returns:
        Sorted unique provider capability names.
    """

    if not agents_path.is_file():
        return []
    text = agents_path.read_text(encoding="utf-8")
    heading_match = re.search(rf"(?m)^{re.escape(REQUIRED_STANDARD_HEADING)}\s*$", text)
    if heading_match is None:
        return []
    next_heading_match = re.search(r"(?m)^## ", text[heading_match.end() :])
    section_end = len(text) if next_heading_match is None else heading_match.end() + next_heading_match.start()
    section = text[heading_match.end() : section_end]
    return sorted(set(re.findall(r"`project-standards:([a-z0-9-]+)`", section)))
