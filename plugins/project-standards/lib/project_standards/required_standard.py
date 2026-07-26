"""Parse declared project standards from canonical repository instructions."""

from __future__ import annotations

from pathlib import Path
import re

MARKDOWN_FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
REQUIRED_STANDARD_HEADING = "## Required Standards"
REQUIRED_STANDARD_NAME_RE = re.compile(r"`project-standards:([a-z0-9-]+)`")


def _fence_close_match(line: str, fence_character: str, fence_length: int) -> bool:
    """Return whether one line closes the active Markdown fence.

    Args:
        line: Candidate Markdown source line.
        fence_character: Backtick or tilde opening character.
        fence_length: Minimum closing fence length.

    Returns:
        Whether the line is one valid closing fence.
    """

    return re.fullmatch(rf" {{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*", line) is not None


def _required_standard_section_line_list_get(text: str) -> list[str]:
    """Return literal lines from the canonical Required Standards section.

    Args:
        text: Complete root instruction text.

    Returns:
        Section lines outside fenced code and HTML comments.
    """

    section_line_list: list[str] = []
    fence_character = ""
    fence_length = 0
    have_html_comment = False
    have_section = False
    for line in text.splitlines():
        if fence_character:
            if _fence_close_match(line, fence_character, fence_length):
                fence_character = ""
                fence_length = 0
            continue
        fence_match = MARKDOWN_FENCE_OPEN_RE.fullmatch(line)
        if fence_match is not None:
            fence = fence_match.group("fence")
            if fence[0] != "`" or "`" not in fence_match.group("info"):
                fence_character = fence[0]
                fence_length = len(fence)
                continue
        if have_html_comment:
            if "-->" in line:
                have_html_comment = False
            continue
        if "<!--" in line:
            if "-->" not in line.split("<!--", maxsplit=1)[1]:
                have_html_comment = True
            continue
        if not have_section:
            have_section = line == REQUIRED_STANDARD_HEADING
            continue
        if line.startswith("## "):
            break
        section_line_list.append(line)
    return section_line_list


def required_standard_name_list_get(agents_path: Path) -> list[str]:
    """Return declared project-standard capability names.

    Args:
        agents_path: Root repository instruction file.

    Returns:
        Sorted unique provider capability names.
    """

    if not agents_path.is_file():
        return []
    text = agents_path.read_text(encoding="utf-8")
    return sorted(
        {
            standard_name
            for line in _required_standard_section_line_list_get(text)
            if line.startswith("- ")
            for standard_name in REQUIRED_STANDARD_NAME_RE.findall(line)
        }
    )
