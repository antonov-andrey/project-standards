"""Test contracts for `plugins/project-standards/skills/python-developer/scripts/python_hidden_dependency_construction_check.py`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from lib.antipattern_check_helpers import ROOT, checker_with_sample_run


def test_hidden_dependency_construction_check_fails_on_runtime_constructor() -> None:
    """Runtime methods must not construct dependencies ad hoc."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_hidden_dependency_construction_check.py",
        src="""
class ApiClient:
    pass


class WorkflowService:
    def run(self):
        client = ApiClient()
        return client
""".strip(),
    )

    assert result.returncode == 1
    assert "hidden dependency construction" in result.stdout


def test_hidden_dependency_construction_check_fails_on_service_locator() -> None:
    """Service-locator calls inside runtime flow must fail."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_hidden_dependency_construction_check.py",
        src="""
class WorkflowService:
    def run(self):
        repo = container.resolve(OrderRepository)
        return repo
""".strip(),
    )

    assert result.returncode == 1
    assert "service-locator resolution" in result.stdout


def test_hidden_dependency_construction_check_passes_on_explicit_factory() -> None:
    """Explicit factories remain allowed."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_hidden_dependency_construction_check.py",
        src="""
class ApiClient:
    pass


def build_client():
    return ApiClient()
""".strip(),
    )

    assert result.returncode == 0
    assert "hidden-dependency construction check passed" in result.stdout.lower()


def test_hidden_dependency_construction_check_rejects_missing_explicit_scope() -> None:
    """Checker must reject a missing explicit scope without traceback."""

    result = subprocess.run(
        [
            "plugins/project-standards/skills/python-developer/scripts/python_hidden_dependency_construction_check.py",
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
