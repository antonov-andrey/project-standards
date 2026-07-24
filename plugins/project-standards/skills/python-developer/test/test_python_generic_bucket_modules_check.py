"""Test contracts for `plugins/project-standards/skills/python-developer/scripts/python_generic_bucket_module_check.py`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from lib.antipattern_check_helpers import ROOT, checker_with_sample_run


def test_generic_bucket_modules_check_fails_on_heterogeneous_bucket_module() -> None:
    """Bucket-named modules with a second heterogeneity signal must fail."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_generic_bucket_module_check.py",
        filename="utils.py",
        src="""
import httpx
import redis
import sqlalchemy

DEFAULT_TIMEOUT = 5


def build_request():
    return httpx.Client()


def read_cache(cache_key):
    return cache_key


class RuntimeState:
    pass
""".strip(),
    )

    assert result.returncode == 1
    assert "generic bucket module" in result.stdout


def test_generic_bucket_modules_check_passes_when_name_alone_is_not_enough() -> None:
    """Bucket names alone must not fail without the second signal."""

    result = checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_generic_bucket_module_check.py",
        filename="utils.py",
        src="""
def normalize_name(value):
    return value.strip().lower()
""".strip(),
    )

    assert result.returncode == 0
    assert "generic bucket-module check passed" in result.stdout.lower()


def test_generic_bucket_modules_check_rejects_missing_explicit_scope() -> None:
    """Checker must reject a missing explicit scope without traceback."""

    result = subprocess.run(
        [
            "plugins/project-standards/skills/python-developer/scripts/python_generic_bucket_module_check.py",
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
