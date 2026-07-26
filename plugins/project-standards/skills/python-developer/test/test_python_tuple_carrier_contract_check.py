"""Behavior tests for provider-owned tuple-carrier checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_tuple_carrier_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run the real tuple checker against one synthetic repository.

    Args:
        project_root: Synthetic Git repository root.
        source: Python source under test.

    Returns:
        Completed checker process.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project_root, check=True)
    (project_root / "module.py").write_text(source, encoding="utf-8")
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
                "path_list": ["module.py"],
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_reports_nested_annotations_runtime_storage_and_return(tmp_path: Path) -> None:
    """Nested tuple annotations and runtime tuple carriers are rejected.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "def example(payload_list: list[tuple[str, int]], left: str, right: str) -> tuple[str, str]:\n"
            '    """Build a forbidden pair."""\n'
            "    pair = (left, right)\n"
            "    return tuple(pair)\n"
        ),
    )

    assert result.returncode == 1
    message_text = "\n".join(json.loads(line)["message"] for line in result.stdout.splitlines())
    assert "parameter payload_list: tuple[str, int]" in message_text
    assert "annotation in return: tuple[str, str]" in message_text
    assert "stores forbidden tuple carrier in pair: (left, right)" in message_text
    assert "returns forbidden tuple carrier expression: tuple(pair)" in message_text
    assert result.stderr == ""


def test_checker_allows_destructuring_and_immutable_constant_tuples(tmp_path: Path) -> None:
    """Destructuring and hardcoded immutable tuple constants remain allowed.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "PAIR = ('a', 'b')\n\n"
            "def example(source_list: list[str]) -> None:\n"
            '    """Use constants and unpacking without a tuple carrier."""\n'
            "    local_pair = ('a', 'b')\n"
            "    left, right = source_list\n"
            "    assert PAIR and local_pair and left and right\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
