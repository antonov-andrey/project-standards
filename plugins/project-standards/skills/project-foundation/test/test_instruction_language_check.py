"""Behavior tests for the provider-owned instruction-language checker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "instruction_language_check.py"
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


def test_checker_rejects_ambiguous_term_but_allows_canonical_owner_rule(tmp_path: Path) -> None:
    """Only the exact writing-rule owner may define the forbidden term.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    owner_path = (
        project_root / "plugins/project-standards/skills/project-foundation/references/writing-and-reporting.md"
    )
    owner_path.parent.mkdir(parents=True)
    owner_path.write_text(
        "The term `repository-owned` is forbidden in instruction artifacts.\n",
        encoding="utf-8",
    )
    (project_root / "AGENTS.md").write_text(
        "# Guidelines\n\nUse repository-owned configuration.\n",
        encoding="utf-8",
    )

    result = _checker_run(
        project_root,
        [
            "AGENTS.md",
            "plugins/project-standards/skills/project-foundation/references/writing-and-reporting.md",
        ],
    )

    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "line": 3,
        "message": (
            "forbidden instruction term `repository-owned`; " "use `project-local` or explicit path-scoped wording"
        ),
        "path": "AGENTS.md",
    }
    assert result.stderr == ""
