"""Behavior tests for canonical Required Standards parsing."""

from pathlib import Path

from project_standards.required_standard import required_standard_name_list_get


def test_parser_reads_grouped_direct_entries_only_from_canonical_section(tmp_path: Path) -> None:
    """The parser returns every declared capability from direct section entries.

    Args:
        tmp_path: Per-test temporary directory.
    """

    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        (
            "# Repository Guidelines\n\n"
            "## Required Standards\n\n"
            "- `project-standards:python-developer` and "
            "`project-standards:pytest-developer` apply to Python.\n"
            "- `project-standards:project-foundation` applies to all work.\n"
            "\n"
            "## Project Contract\n\n"
            "- `project-standards:not-selected` is an example only.\n"
        ),
        encoding="utf-8",
    )

    assert required_standard_name_list_get(agents_path) == [
        "project-foundation",
        "pytest-developer",
        "python-developer",
    ]


def test_parser_ignores_fenced_comment_and_nested_example_tokens(tmp_path: Path) -> None:
    """Code, comments, and nested prose cannot become declared capabilities.

    Args:
        tmp_path: Per-test temporary directory.
    """

    agents_path = tmp_path / "AGENTS.md"
    agents_path.write_text(
        (
            "# Repository Guidelines\n\n"
            "```markdown\n"
            "## Required Standards\n"
            "- `project-standards:fenced-heading` applies.\n"
            "```\n\n"
            "## Required Standards\n\n"
            "<!--\n"
            "- `project-standards:commented` applies.\n"
            "-->\n"
            "```markdown\n"
            "- `project-standards:fenced-entry` applies.\n"
            "```\n"
            "  - `project-standards:nested-example` is not one direct entry.\n"
            "- `project-standards:project-foundation` applies.\n"
        ),
        encoding="utf-8",
    )

    assert required_standard_name_list_get(agents_path) == ["project-foundation"]


def test_parser_returns_empty_for_missing_instruction_or_section(tmp_path: Path) -> None:
    """Missing machine-facing declaration input produces no declared capabilities.

    Args:
        tmp_path: Per-test temporary directory.
    """

    agents_path = tmp_path / "AGENTS.md"
    assert required_standard_name_list_get(agents_path) == []

    agents_path.write_text("# Repository Guidelines\n", encoding="utf-8")
    assert required_standard_name_list_get(agents_path) == []
