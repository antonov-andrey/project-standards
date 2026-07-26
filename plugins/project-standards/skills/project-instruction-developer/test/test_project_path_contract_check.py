"""Behavior tests for Key Directory Map path-contract checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "project_path_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"

AGENTS_TEXT = """# Repository Guidelines

## Key Directory Map

- `backend/`: backend root.
- `lib/`: shared root.
- `plugins/`: plugin provider root.
- `script/<script_name>/`: script-family root.
- `<entrypoint>.py`: root entrypoint.
- `model_sqlalchemy/`: persisted owner root.
- `model_sqlalchemy/__init__.py`: package module.
- `model_sqlalchemy/<database_name>/__init__.py`: database package.
- `model_sqlalchemy/<database_name>/<table_name>.py`: one row model.
- `model_sqlalchemy/<database_name>/mysql/view/*.py`: one MySQL view.
- `model_sqlalchemy/database.py`: database registry.

## Other
"""


def _checker_run(project_root: Path, relative_path_by_source_map: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the real checker against one synthetic project.

    Args:
        project_root: Synthetic Git repository root.
        relative_path_by_source_map: File text keyed by repository path.

    Returns:
        Completed checker process.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project_root, check=True)
    for relative_path, source in relative_path_by_source_map.items():
        path = project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
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
                "path_list": sorted(relative_path_by_source_map),
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_accepts_declared_broad_template_and_entrypoint_paths(tmp_path: Path) -> None:
    """Every supported declaration form matches its intended current path.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "AGENTS.md": AGENTS_TEXT,
            "app.py": '"""Entrypoint."""\n',
            "backend/api.py": '"""Backend."""\n',
            "lib/service.py": '"""Service."""\n',
            "model_sqlalchemy/app/__init__.py": '"""Database package."""\n',
            "model_sqlalchemy/app/item.py": '"""Row model."""\n',
            "model_sqlalchemy/app/mysql/view/current.py": '"""View."""\n',
            "model_sqlalchemy/database.py": '"""Registry."""\n',
            "plugins/provider/lib/package.py": '"""Plugin support."""\n',
            "script/job/workflow.py": '"""Workflow."""\n',
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_undeclared_model_owner_path(tmp_path: Path) -> None:
    """The broad model root does not hide an undeclared child family.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "AGENTS.md": AGENTS_TEXT,
            "model_sqlalchemy/app/random/owner.py": '"""Undeclared owner."""\n',
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert finding_list == [
        {
            "line": 1,
            "message": "Main project Python path is not declared by the Key Directory Map",
            "path": "model_sqlalchemy/app/random/owner.py",
        }
    ]
    assert result.stderr == ""
