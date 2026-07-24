"""Test contracts for plugins/project-standards/skills/python-developer/scripts/python_argument_pack_check.py.

These tests validate fail/warn/allow semantics for argument-pack helper detection.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from lib.antipattern_check_helpers import ROOT, checker_with_sample_run


def _checker_run(tmp_path: Path, src: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the argument-pack checker on one temporary sample file.

    Args:
        tmp_path: Pytest temporary directory. Present for test-call symmetry.
        src: Python source code to analyze.
        args: Additional CLI flags.

    Returns:
        Completed process object for checker invocation.
    """

    del tmp_path
    return checker_with_sample_run(
        checker_relpath="plugins/project-standards/skills/python-developer/scripts/python_argument_pack_check.py",
        src=src,
        extra_args=args,
    )


def test_pass_for_small_pure_helper_signature(tmp_path: Path) -> None:
    """Pass when helper signature is small and non-dependency-like.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        """
def normalize_name(value: str, lang: str) -> str:
    return value.strip().lower() + ":" + lang
""".strip(),
    )

    assert result.returncode == 0
    assert "passed" in result.stdout.lower()


def test_fail_for_argument_explosion_with_dependency_names(tmp_path: Path) -> None:
    """Fail when helper has too many dependency-like arguments.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        """
def run_request(session, repo, client, page, navigation, delay_settings, timeout_ms):
    return session, repo, client, page, navigation, delay_settings, timeout_ms
""".strip(),
        "--max-args",
        "5",
    )

    assert result.returncode == 1
    assert "argument explosion" in result.stdout


def test_warn_for_repeated_dependency_pack(tmp_path: Path) -> None:
    """Warn when two helpers repeat a dependency pack.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        """
def prepare_request(session, client, config, logger):
    return session, client, config, logger


def execute_request(session, client, config, logger):
    return session, client, config, logger
""".strip(),
        "--max-args",
        "12",
        "--min-shared",
        "3",
    )

    assert result.returncode == 0
    assert "repeated dependency-pack" in result.stdout
    assert "warnings" in result.stdout.lower()


def test_fail_for_pseudo_method_helper_callsite(tmp_path: Path) -> None:
    """Fail when method forwards 2+ self fields into helper call.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        """
def helper_run(session, logger, url):
    return session, logger, url


class RequestRunner:
    def __init__(self, session, logger):
        self.session = session
        self.logger = logger

    def run(self, url):
        return helper_run(self.session, self.logger, url)
""".strip(),
        "--max-args",
        "12",
    )

    assert result.returncode == 1
    assert "pseudo-method helper call" in result.stdout


def test_allow_comment_suppresses_fail_and_emits_warning(tmp_path: Path) -> None:
    """Allow marker suppresses fail and keeps warning visibility.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        """
def run_request(session, repo, client, page, navigation, delay_settings, timeout_ms):  # argpack: allow temporary bridge until WI-1234
    return session, repo, client, page, navigation, delay_settings, timeout_ms
""".strip(),
        "--max-args",
        "5",
    )

    assert result.returncode == 0
    assert "allow-override" in result.stdout


def test_allow_comment_without_reason_warns(tmp_path: Path) -> None:
    """Allow marker without reason must produce explicit warning.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        """
def run_request(session, repo, client, page, navigation, delay_settings, timeout_ms):  # argpack: allow
    return session, repo, client, page, navigation, delay_settings, timeout_ms
""".strip(),
        "--max-args",
        "5",
    )

    assert result.returncode == 0
    assert "without reason" in result.stdout


def test_fail_on_repeated_pack_flag_promotes_warning(tmp_path: Path) -> None:
    """`--fail-on-repeated-pack` promotes repeated-pack warning into failure.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        """
def first(session, client, config, logger):
    return session, client, config, logger


def second(session, client, config, logger):
    return session, client, config, logger
""".strip(),
        "--max-args",
        "12",
        "--fail-on-repeated-pack",
    )

    assert result.returncode == 1
    assert "repeated dependency-pack" in result.stdout


def test_parse_args_name_does_not_bypass_argument_pack_check(tmp_path: Path) -> None:
    """`parse_args` must not bypass dependency-pack detection by name alone.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        """
def parse_args(session, repo, client, page, navigation, delay_settings, timeout_ms):
    return session, repo, client, page, navigation, delay_settings, timeout_ms
""".strip(),
        "--max-args",
        "5",
    )

    assert result.returncode == 1
    assert "argument explosion" in result.stdout


def test_parser_suffix_name_does_not_bypass_argument_pack_check(tmp_path: Path) -> None:
    """`*_parser` names must not bypass dependency-pack detection by suffix alone.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        """
def request_parser(session, repo, client, page, navigation, delay_settings, timeout_ms):
    return session, repo, client, page, navigation, delay_settings, timeout_ms
""".strip(),
        "--max-args",
        "5",
    )

    assert result.returncode == 1
    assert "argument explosion" in result.stdout


def test_invalid_explicit_scope_fails_cleanly() -> None:
    """Missing explicit paths must fail cleanly without a traceback."""

    result = subprocess.run(
        [
            "plugins/project-standards/skills/python-developer/scripts/python_argument_pack_check.py",
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
