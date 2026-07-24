"""Test contracts for `plugins/project-standards/skills/python-developer/scripts/python_control_flow_complexity_check.py`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from lib.antipattern_check_helpers import ROOT, checker_with_sample_run


def test_control_flow_complexity_check_fails_on_overloaded_runtime_flow() -> None:
    """Overloaded branch count and nesting must fail."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_control_flow_complexity_check.py",
        src="""
def run(items):
    for item in items:
        if item > 0:
            if item % 2 == 0:
                if item > 10:
                    return item
        elif item < 0:
            return item
    return None
""".strip(),
        extra_args=("--max-branches", "3", "--max-nesting", "2"),
    )

    assert result.returncode == 1
    assert "control-flow complexity exceeds limits" in result.stdout


def test_control_flow_complexity_check_passes_on_small_linear_flow() -> None:
    """Small linear control flow must pass."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_control_flow_complexity_check.py",
        src="""
def run(value):
    if value > 10:
        return value
    return value + 1
""".strip(),
        extra_args=("--max-branches", "3", "--max-nesting", "2"),
    )

    assert result.returncode == 0
    assert "control-flow complexity check passed" in result.stdout.lower()


def test_control_flow_complexity_check_rejects_missing_explicit_scope() -> None:
    """Checker must reject a missing explicit scope without traceback."""

    result = subprocess.run(
        [
            "plugins/project-standards/skills/python-developer/scripts/python_control_flow_complexity_check.py",
            "missing_scope.py",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )

    assert result.returncode == 2
    assert result.stderr.strip() == "ERROR: path does not exist: missing_scope.py"
    assert "Traceback" not in result.stderr
