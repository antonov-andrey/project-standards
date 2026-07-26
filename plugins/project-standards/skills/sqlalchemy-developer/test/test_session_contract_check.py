"""Behavior tests for SQLAlchemy session and bootstrap ownership checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "session_contract_check.py"
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


def _project_create(tmp_path: Path, source: str) -> Path:
    """Create one synthetic Git project with a backend module.

    Args:
        tmp_path: Pytest temporary directory.
        source: Backend module source.

    Returns:
        Synthetic project root.
    """

    project_root = tmp_path / "project"
    backend_path = project_root / "backend" / "service.py"
    backend_path.parent.mkdir(parents=True)
    backend_path.write_text(source, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], check=True, cwd=project_root)
    return project_root


def test_checker_accepts_caller_injected_session_without_readiness_probe(tmp_path: Path) -> None:
    """A class that only uses its injected session opens no hidden DB state.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(
        tmp_path,
        (
            "class Service:\n"
            "    def __init__(self, session):\n"
            "        self._session = session\n\n"
            "    def run(self):\n"
            "        return self._session.get(Item, 'id')\n"
        ),
    )

    result = _checker_run(project_root, ["backend/service.py"])

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_alias_openers_engine_url_probe_and_stale_api(tmp_path: Path) -> None:
    """All reliable session, readiness, and stale-name branches are rejected.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(
        tmp_path,
        (
            "import sqlalchemy as sa\n"
            "from config_sqlalchemy import sqlalchemy_config as project_sqlalchemy_config\n"
            "from sqlalchemy import inspect\n\n"
            "class Service:\n"
            "    def run(self, session):\n"
            "        sa.create_engine('sqlite://')\n"
            "        project_sqlalchemy_config.session_get()\n"
            "        inspect(session.get_bind()).has_table('item')\n"
            "        return session.get_bind().url.database\n"
        ),
    )
    note_path = project_root / "AGENTS.md"
    note_path.write_text("Do not use project_session_scope.\n", encoding="utf-8")

    result = _checker_run(project_root, ["AGENTS.md", "backend/service.py"])

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    message_set = {finding["message"] for finding in finding_list}
    assert "stale project session API name 'project_session_scope' is forbidden" in message_set
    assert "manual sqlalchemy.inspect import is forbidden in Main project code" in message_set
    assert "class Service opens SQLAlchemy state via sa.create_engine(...)" in message_set
    assert "class Service opens SQLAlchemy state via project_sqlalchemy_config.session_get(...)" in message_set
    assert (
        "manual SQLAlchemy table-inspection readiness check inspect(session.get_bind()).has_table is forbidden in Main project code"
        in message_set
    )
    assert "code derives a physical database name from an engine URL" in message_set
    assert result.stderr == ""
