"""Behavior tests for documented script-command environment assignments."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "script_command_documentation_check.py"
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


def test_checker_rejects_inline_environment_and_accepts_plain_script_command(tmp_path: Path) -> None:
    """Inline assignments fail while the same direct command remains valid.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "AGENTS.md").write_text(
        ("# Guidelines\n\n" "```bash\n" "PYTHONPATH=. tool/run.py --help\n" "tool/run.py --help\n" "```\n"),
        encoding="utf-8",
    )

    result = _checker_run(project_root, ["AGENTS.md"])

    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "line": 4,
        "message": "script command must not use inline environment assignment `PYTHONPATH=. tool/run.py`",
        "path": "AGENTS.md",
    }
    assert result.stderr == ""
