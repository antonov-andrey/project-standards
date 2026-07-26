"""Behavior tests for the repository-reference checker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "repository_reference_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_list: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the real checker process against one synthetic repository.

    Args:
        project_root: Exact synthetic repository root.
        relative_path_list: Current repository-relative path list.

    Returns:
        Completed checker process.
    """

    environment_map = os.environ.copy()
    environment_map["PYTHONPATH"] = str(PACKAGE_ROOT)
    return subprocess.run(
        [sys.executable, str(CHECKER_PATH)],
        capture_output=True,
        check=False,
        cwd=project_root,
        env=environment_map,
        input=json.dumps(
            {
                "path_list": sorted(relative_path_list),
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_accepts_root_paths_toc_anchors_and_non_reference_syntax(tmp_path: Path) -> None:
    """Canonical references and the critical ignored forms produce no findings.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    skill_root = project_root / "plugins" / "demo" / "skills" / "sample"
    skill_root.mkdir(parents=True)
    (project_root / "AGENTS.md").write_text(
        (
            "# Guidelines\n\n"
            "## Table Of Contents\n\n"
            "- [Rules](#rules)\n\n"
            "## Rules\n\n"
            "Use `plugins/demo/skills/sample/SKILL.md`.\n"
            'Shell: `export PATH="./.venv/bin:.:$PATH"`.\n'
            "## Key Directory Map\n\n"
            "```text\n"
            "project/\n"
            "  missing.md\n"
            "```\n"
        ),
        encoding="utf-8",
    )
    (skill_root / "SKILL.md").write_text(
        "---\nname: sample\ndescription: Use when testing.\n---\n\n" '{% include "_include/missing.md.j2" %}\n',
        encoding="utf-8",
    )

    result = _checker_run(
        project_root,
        ["AGENTS.md", "plugins/demo/skills/sample/SKILL.md"],
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_rejects_relative_bare_broken_and_markdown_link_references(tmp_path: Path) -> None:
    """Every primary forbidden repository-reference form reports its source line.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    skill_root = project_root / "plugins" / "demo" / "skills" / "sample"
    reference_root = skill_root / "references"
    reference_root.mkdir(parents=True)
    (reference_root / "protocol.md").write_text("# Protocol\n", encoding="utf-8")
    (project_root / "AGENTS.md").write_text(
        (
            "# Guidelines\n\n"
            "Use `./plugins/demo/skills/sample/SKILL.md`.\n"
            "Use `protocol.md`.\n"
            "Use `plugins/missing/SKILL.md`.\n"
            "[protocol](plugins/demo/skills/sample/references/protocol.md)\n"
        ),
        encoding="utf-8",
    )
    (skill_root / "SKILL.md").write_text("# Sample\n", encoding="utf-8")

    result = _checker_run(
        project_root,
        [
            "AGENTS.md",
            "plugins/demo/skills/sample/SKILL.md",
            "plugins/demo/skills/sample/references/protocol.md",
        ],
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert {(finding["line"], finding["message"]) for finding in finding_list if finding["path"] == "AGENTS.md"} == {
        (
            3,
            "repository-local references must be plain root-relative: " "plugins/demo/skills/sample/SKILL.md",
        ),
        (
            4,
            "repository-local references must be plain root-relative: "
            "plugins/demo/skills/sample/references/protocol.md",
        ),
        (5, "referenced path does not exist: plugins/missing/SKILL.md"),
        (
            6,
            "repository-local Markdown links are forbidden; use one plain root-relative reference: "
            "plugins/demo/skills/sample/references/protocol.md",
        ),
    }
    assert result.stderr == ""


def test_checker_rejects_same_file_anchor_outside_table_of_contents(tmp_path: Path) -> None:
    """Same-file Markdown anchors are exceptional only inside the explicit TOC.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "AGENTS.md").write_text("# Guidelines\n\nSee [rules](#rules).\n", encoding="utf-8")

    result = _checker_run(project_root, ["AGENTS.md"])

    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "line": 3,
        "message": "repository-local Markdown links are allowed only for same-file table-of-contents anchors",
        "path": "AGENTS.md",
    }
