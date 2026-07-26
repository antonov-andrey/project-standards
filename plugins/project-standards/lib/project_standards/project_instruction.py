"""Parse machine-relevant declarations from canonical project instructions."""

from __future__ import annotations

from pathlib import Path
import re

KEY_DIRECTORY_MAP_HEADING = "## Key Directory Map"
PATH_TEMPLATE_BULLET_PATTERN = re.compile(r"^- `([^`]+)`:")
PATH_TEMPLATE_PARAMETER_PATTERN = re.compile(r"<[^/>]+>")


def key_directory_map_path_template_list_get(agents_path: Path) -> list[str]:
    """Return path templates declared by the Key Directory Map.

    Args:
        agents_path: Canonical repository instruction path.

    Returns:
        Declared path labels in source order without duplicates.
    """

    if not agents_path.is_file():
        return []
    line_list = agents_path.read_text(encoding="utf-8").splitlines()
    in_section = False
    path_template_list: list[str] = []
    for line in line_list:
        if line.strip() == KEY_DIRECTORY_MAP_HEADING:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        match = PATH_TEMPLATE_BULLET_PATTERN.match(line)
        if match is None or match.group(1) in path_template_list:
            continue
        path_template_list.append(match.group(1))
    return path_template_list


def match_path_template(relative_path: str, path_template: str) -> bool:
    """Return whether one current path matches one declared file template.

    Args:
        relative_path: Repository-relative current file path.
        path_template: Key Directory Map file template.

    Returns:
        Whether parameters and wildcards match complete path segments.
    """

    if path_template.endswith("/"):
        return False
    pattern_part_list: list[str] = []
    for part in path_template.split("/"):
        escaped_part = re.escape(part)
        escaped_part = PATH_TEMPLATE_PARAMETER_PATTERN.sub("[^/]+", escaped_part)
        escaped_part = escaped_part.replace(r"\*", "[^/]*")
        pattern_part_list.append(escaped_part)
    return re.fullmatch("/".join(pattern_part_list), relative_path) is not None


def match_path_template_directory(relative_path: str, path_template: str) -> bool:
    """Return whether one current path descends from a declared directory template.

    Args:
        relative_path: Repository-relative current file path.
        path_template: Key Directory Map directory template ending in `/`.

    Returns:
        Whether the complete declared directory prefix matches.
    """

    if not path_template.endswith("/"):
        return False
    directory_template = path_template.removesuffix("/")
    pattern_part_list: list[str] = []
    for part in directory_template.split("/"):
        escaped_part = re.escape(part)
        escaped_part = PATH_TEMPLATE_PARAMETER_PATTERN.sub("[^/]+", escaped_part)
        escaped_part = escaped_part.replace(r"\*", "[^/]*")
        pattern_part_list.append(escaped_part)
    return re.fullmatch(f"{'/'.join(pattern_part_list)}/.+", relative_path) is not None
