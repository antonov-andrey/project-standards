#!/usr/bin/env python3
"""Check root-relative references in project-local instruction assets."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.instruction_asset import instruction_text_relpath_list_get, instruction_text_sanitize
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

EXTERNAL_TARGET_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
INLINE_LINK_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)|\[[^\]]+\]\(([^)]+)\)")
INVALID_RELATIVE_REFERENCE_PREFIX = "__INVALID_RELATIVE_REFERENCE__:"
PATH_TOKEN_PATTERN = re.compile(
    r"(?:\.{1,2}/)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.<>{}-]+)+|" r"[A-Za-z0-9_.-]+\.(?:md|py|toml|yaml|yml|json|txt|j2)"
)
ROOT_REFERENCE_FILE_SUFFIX_SET = {".j2", ".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
SCANNED_INSTRUCTION_SUFFIX_SET = {".j2", ".md", ".txt"}


def _exist_repository_target(normalized_target: str, repository_relative_path_set: set[str]) -> bool:
    """Return whether one current file or represented directory matches a target.

    Args:
        normalized_target: Canonical root-relative target.
        repository_relative_path_set: Current non-ignored repository paths.

    Returns:
        Whether the target is a current file or ancestor directory.
    """

    return normalized_target in repository_relative_path_set or any(
        relative_path.startswith(f"{normalized_target}/") for relative_path in repository_relative_path_set
    )


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return all repository-reference findings.

    Args:
        request: Validated checker process request.

    Returns:
        Broken, relative, and forbidden Markdown-link findings.
    """

    project_root = Path(request["project_root"])
    relative_path_list = request["path_list"]
    file_relative_path_set = {
        relative_path for relative_path in relative_path_list if (project_root / relative_path).exists()
    }
    root_entry_name_set = {
        Path(relative_path).parts[0] for relative_path in file_relative_path_set if Path(relative_path).parts
    }
    root_file_name_set = {
        Path(relative_path).name
        for relative_path in file_relative_path_set
        if len(Path(relative_path).parts) == 1 and Path(relative_path).suffix.lower() in ROOT_REFERENCE_FILE_SUFFIX_SET
    }
    root_file_name_set.add("AGENTS.md")
    relative_path_list_by_file_name_map: dict[str, list[str]] = {}
    for relative_path in file_relative_path_set:
        if Path(relative_path).suffix.lower() not in ROOT_REFERENCE_FILE_SUFFIX_SET:
            continue
        relative_path_list_by_file_name_map.setdefault(Path(relative_path).name, []).append(relative_path)
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in instruction_text_relpath_list_get(project_root, relative_path_list):
        if Path(relative_path).suffix.lower() not in SCANNED_INSTRUCTION_SUFFIX_SET:
            continue
        text = (project_root / relative_path).read_text(encoding="utf-8")
        finding_list.extend(
            _markdown_link_finding_list_get(
                project_root,
                relative_path,
                text,
                file_relative_path_set,
                relative_path_list_by_file_name_map,
                root_entry_name_set,
                root_file_name_set,
            )
        )
        finding_list.extend(
            _path_token_finding_list_get(
                project_root,
                relative_path,
                _markdown_link_target_strip(instruction_text_sanitize(text)),
                file_relative_path_set,
                relative_path_list_by_file_name_map,
                root_entry_name_set,
                root_file_name_set,
            )
        )
    return finding_list


def _markdown_code_strip(text: str) -> str:
    """Blank fenced and inline code while preserving line count.

    Args:
        text: Raw Markdown-compatible instruction text.

    Returns:
        Text whose code examples cannot be mistaken for rendered links.
    """

    in_fence = False
    result_line_list: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            result_line_list.append("\n" if line.endswith("\n") else "")
            continue
        if in_fence:
            result_line_list.append("\n" if line.endswith("\n") else "")
            continue
        result_line_list.append(re.sub(r"`[^`\n]*`", "", line))
    return "".join(result_line_list)


def _markdown_link_finding_list_get(
    project_root: Path,
    relative_path: str,
    text: str,
    file_relative_path_set: set[str],
    relative_path_list_by_file_name_map: Mapping[str, list[str]],
    root_entry_name_set: set[str],
    root_file_name_set: set[str],
) -> list[ProjectStandardCheckerFinding]:
    """Return forbidden repository-local Markdown link findings.

    Args:
        project_root: Exact target repository root.
        relative_path: Instruction document path.
        text: Raw instruction document text.
        file_relative_path_set: Current repository file paths.
        relative_path_list_by_file_name_map: Current paths keyed by basename.
        root_entry_name_set: Current root entry names.
        root_file_name_set: Current root-level reference filenames.

    Returns:
        Local Markdown links outside the explicit table of contents.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    in_table_of_contents = False
    for line_number, line in enumerate(_markdown_code_strip(text).splitlines(), start=1):
        if line.strip() == "## Table Of Contents":
            in_table_of_contents = True
        elif in_table_of_contents and line.startswith("## "):
            in_table_of_contents = False
        for match in INLINE_LINK_PATTERN.finditer(line):
            raw_target = (match.group(1) or match.group(2) or "").strip()
            if raw_target.startswith("<") and raw_target.endswith(">"):
                raw_target = raw_target[1:-1].strip()
            if not raw_target or EXTERNAL_TARGET_PATTERN.match(raw_target) or raw_target.startswith("~/.codex/skills/"):
                continue
            if raw_target.startswith("#") and in_table_of_contents:
                continue
            target = raw_target.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0].strip()
            if not target:
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=line_number,
                        message="repository-local Markdown links are allowed only for same-file table-of-contents anchors",
                        path=relative_path,
                    )
                )
                continue
            normalized_target = _reference_normalize(
                project_root,
                relative_path,
                target,
                file_relative_path_set,
                relative_path_list_by_file_name_map,
                root_entry_name_set,
                root_file_name_set,
            )
            finding_list.append(
                ProjectStandardCheckerFinding(
                    line=line_number,
                    message=(
                        "repository-local Markdown links are forbidden; use one plain root-relative reference"
                        + (
                            f": {normalized_target.removeprefix(INVALID_RELATIVE_REFERENCE_PREFIX)}"
                            if normalized_target
                            else ""
                        )
                    ),
                    path=relative_path,
                )
            )
    return finding_list


def _markdown_link_target_strip(text: str) -> str:
    """Blank Markdown link syntax while preserving line count.

    Args:
        text: Instruction text.

    Returns:
        Text without link targets that have their own validation.
    """

    return INLINE_LINK_PATTERN.sub("", text)


def _path_token_finding_list_get(
    project_root: Path,
    relative_path: str,
    text: str,
    file_relative_path_set: set[str],
    relative_path_list_by_file_name_map: Mapping[str, list[str]],
    root_entry_name_set: set[str],
    root_file_name_set: set[str],
) -> list[ProjectStandardCheckerFinding]:
    """Return invalid plain-reference token findings.

    Args:
        project_root: Exact target repository root.
        relative_path: Instruction document path.
        text: Sanitized instruction text.
        file_relative_path_set: Current repository file paths.
        relative_path_list_by_file_name_map: Current paths keyed by basename.
        root_entry_name_set: Current root entry names.
        root_file_name_set: Current root-level reference filenames.

    Returns:
        Relative or broken root-reference findings.
    """

    finding_list: list[ProjectStandardCheckerFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in PATH_TOKEN_PATTERN.finditer(line):
            if match.start() > 0 and line[match.start() - 1] in {"=", "~", "/"}:
                continue
            if "such as " in line[: match.start()].lower() or line[match.end() :].startswith(("/**", "**")):
                continue
            normalized_target = _reference_normalize(
                project_root,
                relative_path,
                match.group(0),
                file_relative_path_set,
                relative_path_list_by_file_name_map,
                root_entry_name_set,
                root_file_name_set,
            )
            if normalized_target is None:
                continue
            if normalized_target.startswith(INVALID_RELATIVE_REFERENCE_PREFIX):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=line_number,
                        message=(
                            "repository-local references must be plain root-relative: "
                            f"{normalized_target.removeprefix(INVALID_RELATIVE_REFERENCE_PREFIX)}"
                        ),
                        path=relative_path,
                    )
                )
            elif not _exist_repository_target(normalized_target, file_relative_path_set):
                finding_list.append(
                    ProjectStandardCheckerFinding(
                        line=line_number,
                        message=f"referenced path does not exist: {normalized_target}",
                        path=relative_path,
                    )
                )
    return finding_list


def _reference_normalize(
    project_root: Path,
    source_relative_path: str,
    raw_target: str,
    file_relative_path_set: set[str],
    relative_path_list_by_file_name_map: Mapping[str, list[str]],
    root_entry_name_set: set[str],
    root_file_name_set: set[str],
) -> str | None:
    """Normalize one path token or classify it as irrelevant.

    Args:
        project_root: Exact target repository root.
        source_relative_path: Instruction file that contains the token.
        raw_target: Raw candidate path token.
        file_relative_path_set: Current repository file paths.
        relative_path_list_by_file_name_map: Current paths keyed by basename.
        root_entry_name_set: Current root entry names.
        root_file_name_set: Current root-level reference filenames.

    Returns:
        Root-relative path, invalid-relative marker, or `None`.
    """

    target = raw_target.strip("`'\",:;()[]{}")
    while target.endswith("."):
        target = target[:-1]
    if (
        not target
        or target in {"./.venv/bin", ".venv/bin"}
        or target.startswith("~/.codex/skills/")
        or any(symbol in target for symbol in ("*", "?", "<", ">", "{", "}", ":"))
    ):
        return None
    source_directory = (project_root / source_relative_path).parent
    file_like_target = Path(target).suffix.lower() in ROOT_REFERENCE_FILE_SUFFIX_SET
    if target.startswith(("./", "../")):
        normalized_path = (source_directory / target).resolve()
        if not normalized_path.is_relative_to(project_root):
            return None
        normalized_target = normalized_path.relative_to(project_root).as_posix()
        if file_like_target or normalized_target in file_relative_path_set:
            return f"{INVALID_RELATIVE_REFERENCE_PREFIX}{normalized_target}"
        return None
    if "/" in target:
        if target.split("/", maxsplit=1)[0] in root_entry_name_set:
            return Path(target).as_posix()
        normalized_path = (source_directory / target).resolve()
        if normalized_path.is_relative_to(project_root):
            normalized_target = normalized_path.relative_to(project_root).as_posix()
            source_part_tuple = Path(source_relative_path).parts
            if (
                len(source_part_tuple) >= 4
                and source_part_tuple[0] == "plugins"
                and source_part_tuple[2] == "skills"
                and normalized_path.is_relative_to(project_root.joinpath(*source_part_tuple[:4]))
                and _exist_repository_target(normalized_target, file_relative_path_set)
            ):
                return normalized_target
            if _exist_repository_target(normalized_target, file_relative_path_set):
                return f"{INVALID_RELATIVE_REFERENCE_PREFIX}{normalized_target}"
        return None
    if target in root_file_name_set:
        return target
    source_local_target = (source_directory / target).resolve()
    if source_local_target.is_relative_to(project_root):
        normalized_target = source_local_target.relative_to(project_root).as_posix()
        source_part_tuple = Path(source_relative_path).parts
        if (
            len(source_part_tuple) >= 4
            and source_part_tuple[0] == "plugins"
            and source_part_tuple[2] == "skills"
            and source_local_target.is_relative_to(project_root.joinpath(*source_part_tuple[:4]))
            and _exist_repository_target(normalized_target, file_relative_path_set)
        ):
            return normalized_target
        if _exist_repository_target(normalized_target, file_relative_path_set):
            return f"{INVALID_RELATIVE_REFERENCE_PREFIX}{normalized_target}"
    matching_relative_path_list = sorted(relative_path_list_by_file_name_map.get(target, []))
    if matching_relative_path_list:
        return f"{INVALID_RELATIVE_REFERENCE_PREFIX}{matching_relative_path_list[0]}"
    return None


def main() -> int:
    """Run the repository-reference checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
