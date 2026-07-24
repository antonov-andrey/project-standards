"""Test contracts for `plugins/project-standards/skills/python-developer/scripts/python_single_use_artifact_check.py`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from lib.antipattern_check_helpers import ROOT, checker_with_sample_run


def test_single_use_artifacts_check_fails_on_single_use_wrapper() -> None:
    """Single-use thin constructor wrappers must fail."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_single_use_artifact_check.py",
        src="""
class Worker:
    def __init__(self, value, enabled):
        self.value = value
        self.enabled = enabled


def build_worker(value):
    return Worker(value, enabled=True)


result = build_worker(1)
""".strip(),
    )

    assert result.returncode == 1
    assert "single-use thin constructor/profile call_wrap function is forbidden" in result.stdout


def test_single_use_artifacts_check_passes_when_wrapper_has_multiple_callsites() -> None:
    """Wrapper candidates used multiple times must not be flagged as single-use."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_single_use_artifact_check.py",
        src="""
class Worker:
    def __init__(self, value, enabled):
        self.value = value
        self.enabled = enabled


def build_worker(value):
    return Worker(value, enabled=True)


first = build_worker(1)
second = build_worker(2)
""".strip(),
    )

    assert result.returncode == 0
    assert "Python single-use artifact check passed." in result.stdout


def test_single_use_artifacts_check_rejects_missing_explicit_scope() -> None:
    """Single-use checker must reject a missing explicit scope without traceback."""

    result = subprocess.run(
        [
            "plugins/project-standards/skills/python-developer/scripts/python_single_use_artifact_check.py",
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
