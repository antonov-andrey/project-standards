"""Resolve and sanitize project-local instruction text assets for checkers."""

from __future__ import annotations

from pathlib import Path
import re

from project_standards.git_repository import submodule_name_by_path_map_get

JINJA_TEMPLATE_STATEMENT_PATTERN = re.compile(r"\{%\s*(?:include|import|extends|from)\b[^\n]*?%\}")
TEXT_FILE_SUFFIX_SET = {".j2", ".json", ".md", ".toml", ".txt", ".yaml", ".yml"}


def _is_instruction_text_path(relative_path: str) -> bool:
    """Return whether one path is an instruction or owner-local template.

    Args:
        relative_path: Repository-relative current file path.

    Returns:
        Whether shared instruction checks apply to the file.
    """

    path = Path(relative_path)
    if path.name.startswith("AGENTS") and path.suffix == ".md":
        return True
    part_tuple = path.parts
    if part_tuple[:2] == (".codex", "skills"):
        return len(part_tuple) >= 3 and part_tuple[2] != ".system"
    if part_tuple[:2] == (".codex", "agents"):
        return True
    if len(part_tuple) >= 4 and part_tuple[0] == "plugins" and part_tuple[2] == "skills":
        return True
    return len(part_tuple) >= 5 and part_tuple[0] == "plugins" and part_tuple[2] == "lib" and "template" in part_tuple


def _is_under_root_list(relative_path: str, root_relative_path_list: list[str]) -> bool:
    """Return whether one path belongs to any declared direct root.

    Args:
        relative_path: Repository-relative path.
        root_relative_path_list: Direct root paths.

    Returns:
        Whether the path equals or descends from one root.
    """

    return any(
        relative_path == root_relative_path or relative_path.startswith(f"{root_relative_path}/")
        for root_relative_path in root_relative_path_list
    )


def instruction_text_relpath_list_get(project_root: Path, relative_path_list: list[str]) -> list[str]:
    """Return current root-owned instruction text paths.

    Args:
        project_root: Exact target repository root.
        relative_path_list: Manifest-selected current paths.

    Returns:
        Sorted instruction, Skill, template, and agent text paths.
    """

    submodule_relative_path_list = list(submodule_name_by_path_map_get(project_root))
    return sorted(
        relative_path
        for relative_path in relative_path_list
        if (project_root / relative_path).is_file()
        and Path(relative_path).suffix.lower() in TEXT_FILE_SUFFIX_SET
        and not _is_under_root_list(relative_path, submodule_relative_path_list)
        and _is_instruction_text_path(relative_path)
    )


def _key_directory_map_tree_strip(text: str) -> str:
    """Blank one Key Directory Map fenced tree while preserving line count.

    Args:
        text: Markdown instruction source.

    Returns:
        Source whose structural tree lines are empty.
    """

    line_list = text.splitlines(keepends=True)
    in_key_directory_map = False
    in_tree_fence = False
    result_line_list: list[str] = []
    for line in line_list:
        stripped_line = line.strip()
        if stripped_line == "## Key Directory Map":
            in_key_directory_map = True
            result_line_list.append(line)
            continue
        if in_key_directory_map and not in_tree_fence and stripped_line.startswith("```"):
            in_tree_fence = True
            result_line_list.append(line)
            continue
        if in_tree_fence:
            if stripped_line.startswith("```"):
                in_tree_fence = False
                in_key_directory_map = False
                result_line_list.append(line)
            else:
                result_line_list.append("\n" if line.endswith("\n") else "")
            continue
        if in_key_directory_map and stripped_line.startswith("## "):
            in_key_directory_map = False
        result_line_list.append(line)
    return "".join(result_line_list)


def instruction_text_sanitize(text: str) -> str:
    """Remove structural tree and Jinja syntax from reference scanning.

    Args:
        text: Raw instruction text.

    Returns:
        Text with line positions preserved for reliable diagnostics.
    """

    return JINJA_TEMPLATE_STATEMENT_PATTERN.sub("", _key_directory_map_tree_strip(text))
