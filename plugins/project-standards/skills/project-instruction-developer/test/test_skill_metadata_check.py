"""Behavior tests for the exact skill OpenAI metadata checker."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "skill_metadata_check.py"


def _checker_run(project_root: Path, path_list: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the checker against one synthetic project scope.

    Args:
        project_root: Synthetic project root.
        path_list: Repository-relative metadata paths.

    Returns:
        Completed checker subprocess.
    """

    request = {
        "path_list": path_list,
        "project_root": str(project_root),
        "protocol_version": 1,
        "scope": "all",
    }
    return subprocess.run(
        [sys.executable, str(CHECKER_PATH)],
        capture_output=True,
        check=False,
        input=json.dumps(request),
        text=True,
    )


def _metadata_write(
    project_root: Path,
    *,
    default_prompt: str,
    short_description: str,
    skill_path: str = ".agents/skills/sample",
) -> str:
    """Write one metadata fixture and return its relative path.

    Args:
        project_root: Synthetic project root.
        default_prompt: Default prompt fixture.
        short_description: Short description fixture.
        skill_path: Repository-relative skill root.

    Returns:
        Repository-relative metadata path.
    """

    metadata_path = project_root / skill_path / "agents" / "openai.yaml"
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text(
        (
            "interface:\n"
            f"  short_description: {json.dumps(short_description)}\n"
            f"  default_prompt: {json.dumps(default_prompt)}\n"
        ),
        encoding="utf-8",
    )
    return metadata_path.relative_to(project_root).as_posix()


@pytest.mark.parametrize("description_length", [25, 64])
@pytest.mark.parametrize(
    "skill_path",
    [
        ".agents/skills/sample",
        "plugins/provider/skills/sample",
    ],
)
def test_checker_accepts_prompt_invocation_and_description_boundaries(
    tmp_path: Path,
    description_length: int,
    skill_path: str,
) -> None:
    """Both skill root families accept inclusive description boundaries.

    Args:
        tmp_path: Pytest temporary directory.
        description_length: Inclusive boundary under test.
        skill_path: Provider or project-local skill root.
    """

    relative_path = _metadata_write(
        tmp_path,
        default_prompt="Use $sample for this task.",
        short_description="x" * description_length,
        skill_path=skill_path,
    )

    result = _checker_run(tmp_path, [relative_path])

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.parametrize("description_length", [24, 65])
def test_checker_reports_missing_invocation_and_description_outside_boundaries(
    tmp_path: Path,
    description_length: int,
) -> None:
    """Both exact metadata violations are reported together.

    Args:
        tmp_path: Pytest temporary directory.
        description_length: Invalid boundary under test.
    """

    relative_path = _metadata_write(
        tmp_path,
        default_prompt="Use this skill.",
        short_description="x" * description_length,
    )

    result = _checker_run(tmp_path, [relative_path])

    assert result.returncode == 1
    message_list = [json.loads(line)["message"] for line in result.stdout.splitlines()]
    assert message_list == [
        "interface.default_prompt must contain exact invocation $sample",
        "interface.short_description must contain from 25 through 64 characters",
    ]
    assert result.stderr == ""


def test_checker_reports_malformed_yaml_as_finding(tmp_path: Path) -> None:
    """Malformed metadata is repository evidence, not checker failure.

    Args:
        tmp_path: Pytest temporary directory.
    """

    metadata_path = tmp_path / ".agents" / "skills" / "sample" / "agents" / "openai.yaml"
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text("interface: [\n", encoding="utf-8")
    relative_path = metadata_path.relative_to(tmp_path).as_posix()

    result = _checker_run(tmp_path, [relative_path])

    assert result.returncode == 1
    finding = json.loads(result.stdout)
    assert finding["path"] == relative_path
    assert finding["message"].startswith("agents/openai.yaml must be readable YAML:")
    assert result.stderr == ""
