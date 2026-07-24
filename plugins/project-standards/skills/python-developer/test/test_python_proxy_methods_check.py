"""Test contracts for `plugins/project-standards/skills/python-developer/scripts/python_proxy_method_check.py`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from lib.antipattern_check_helpers import ROOT, checker_with_sample_run


def test_proxy_methods_check_fails_on_pure_pass_through_method() -> None:
    """Pure pass-through instance proxies must fail."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_proxy_method_check.py",
        src="""
class Service:
    def run_impl(self, value):
        return value * 2

    def run(self, value):
        return self.run_impl(value)
""".strip(),
    )

    assert result.returncode == 1
    assert "pure pass-through proxy" in result.stdout


def test_proxy_methods_check_passes_when_method_has_real_logic() -> None:
    """Methods with real local logic must not be flagged as pure proxies."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_proxy_method_check.py",
        src="""
class Service:
    def run_impl(self, value):
        return value * 2

    def run(self, value):
        prepared = value + 1
        return self.run_impl(prepared)
""".strip(),
    )

    assert result.returncode == 0
    assert "Python proxy-method check passed." in result.stdout


def test_proxy_methods_check_allows_main_boundary_wrapper() -> None:
    """Top-level `main` boundary wrappers must remain exempt from proxy findings."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_proxy_method_check.py",
        src="""
def app_run():
    return 7


def main():
    return app_run()
""".strip(),
    )

    assert result.returncode == 0
    assert "Python proxy-method check passed." in result.stdout


def test_proxy_methods_check_rejects_missing_explicit_scope() -> None:
    """Proxy checker must reject a missing explicit scope without traceback."""

    result = subprocess.run(
        ["plugins/project-standards/skills/python-developer/scripts/python_proxy_method_check.py", "missing_scope.py"],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )

    assert result.returncode == 2
    assert result.stderr.strip() == "ERROR: path does not exist: missing_scope.py"
    assert "Traceback" not in result.stderr
