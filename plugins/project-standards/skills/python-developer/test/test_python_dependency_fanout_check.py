"""Test contracts for `plugins/project-standards/skills/python-developer/scripts/python_dependency_fanout_check.py`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from lib.antipattern_check_helpers import ROOT, checker_with_sample_run


def test_dependency_fanout_check_fails_on_dependency_heavy_class() -> None:
    """Classes with too many dependency-like collaborators must fail."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_dependency_fanout_check.py",
        src="""
class WorkflowService:
    def __init__(self, repo, client, session, logger, config, cache):
        self.repo = repo
        self.client = client
        self.session = session
        self.logger = logger
        self.config = config
        self.cache = cache
""".strip(),
        extra_args=("--max-dependencies", "4"),
    )

    assert result.returncode == 1
    assert "class dependency fan-out exceeds limit" in result.stdout


def test_dependency_fanout_check_passes_on_small_owner_surface() -> None:
    """Small collaborator surfaces must pass."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_dependency_fanout_check.py",
        src="""
class WorkflowService:
    def __init__(self, repo, client):
        self.repo = repo
        self.client = client
""".strip(),
        extra_args=("--max-dependencies", "4"),
    )

    assert result.returncode == 0
    assert "dependency fan-out check passed" in result.stdout.lower()


def test_dependency_fanout_check_rejects_missing_explicit_scope() -> None:
    """Checker must reject a missing explicit scope without traceback."""

    result = subprocess.run(
        [
            "plugins/project-standards/skills/python-developer/scripts/python_dependency_fanout_check.py",
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
