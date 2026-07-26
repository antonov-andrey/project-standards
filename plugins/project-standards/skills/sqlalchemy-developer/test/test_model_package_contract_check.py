"""Behavior tests for model_sqlalchemy package checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "model_package_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_by_source_map: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the real checker against synthetic model modules.

    Args:
        project_root: Synthetic Git repository root.
        relative_path_by_source_map: Python source keyed by repository path.

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


def test_checker_accepts_row_database_root_and_empty_support_package_surfaces(tmp_path: Path) -> None:
    """Canonical model package surfaces pass without importing runtime dependencies.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "model_sqlalchemy/__init__.py": (
                '"""Root."""\n\n'
                "from model_sqlalchemy.app import Item\n"
                "from model_sqlalchemy.database import AppDatabase, project_database_list\n\n"
                '__all__ = ["AppDatabase", "Item", "project_database_list"]\n'
            ),
            "model_sqlalchemy/app/__init__.py": (
                '"""Database."""\n\n' "from model_sqlalchemy.app.item import Item\n\n" '__all__ = ["Item"]\n'
            ),
            "model_sqlalchemy/app/item.py": (
                '"""Row."""\n\n' "class Item(ProductOrmBase):\n" "    __tablename__ = 'item'\n"
            ),
            "model_sqlalchemy/app/mysql/view/__init__.py": '"""Views."""\n\n__all__: list[str] = []\n',
            "model_sqlalchemy/database.py": (
                '"""Registry."""\n\n'
                "def project_database_list() -> list[object]:\n"
                "    return []\n\n"
                "class AppDatabase(Database):\n"
                "    pass\n"
            ),
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_row_identity_and_non_model_package_exports(tmp_path: Path) -> None:
    """Wrong table identity and leaked helper surfaces report.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "model_sqlalchemy/__init__.py": (
                '"""Root."""\n\n' "from model_sqlalchemy.database import helper\n\n" '__all__ = ["helper"]\n'
            ),
            "model_sqlalchemy/app/__init__.py": (
                '"""Database."""\n\n' "from model_sqlalchemy.app.item import helper\n\n" '__all__ = ["helper"]\n'
            ),
            "model_sqlalchemy/app/item.py": (
                '"""Row."""\n\n'
                "def helper() -> None:\n"
                "    pass\n\n"
                "class Item(ProductOrmBase):\n"
                "    __tablename__ = 'wrong'\n"
            ),
            "model_sqlalchemy/app/mysql/view/__init__.py": '"""Views."""\n\n__all__ = ["CurrentView"]\n',
            "model_sqlalchemy/database.py": '"""Registry."""\n\n\ndef helper() -> None:\n    pass\n',
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    message_text = "\n".join(finding["message"] for finding in finding_list)
    assert "Item.__tablename__ must equal module stem 'item'" in message_text
    assert "database package export helper is not one row ORM model" in message_text
    assert "root package export helper is not one database registry contract" in message_text
    assert "support-object package must not define named exports" in message_text
    assert result.stderr == ""
