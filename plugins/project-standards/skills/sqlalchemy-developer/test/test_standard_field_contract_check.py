"""Behavior tests for reusable project ORM field and index checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "standard_field_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(
    project_root: Path,
    relative_path_by_source_map: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run the real checker against one synthetic Git repository.

    Args:
        project_root: Exact synthetic repository root.
        relative_path_by_source_map: Source text keyed by repository path.

    Returns:
        Completed checker process.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], check=True, cwd=project_root)
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


def _standard_field_source_get() -> str:
    """Return one complete synthetic standard factory family.

    Returns:
        Source declaring every field needed by standard index generation.
    """

    return (
        "def model_id_column_get():\n"
        "    return mapped_column()\n\n"
        "def model_is_deleted_column_get():\n"
        "    return mapped_column()\n\n"
        "def model_name_column_get():\n"
        "    return mapped_column()\n\n"
        "def model_t_create_column_get(**kwargs):\n"
        "    return mapped_column(**kwargs)\n\n"
        "def model_t_update_column_get():\n"
        "    return mapped_column()\n\n"
        "def model_zitadel_user_id_column_get():\n"
        "    return mapped_column()\n"
    )


def _standard_table_source_get() -> str:
    """Return canonical synthetic shared index generation.

    Returns:
        Source declaring every required index signature.
    """

    return (
        "def model_table_arg_list_get(table_name):\n"
        "    return [\n"
        "        Index(f'ix_{table_name}_zitadel_user_id', 'zitadel_user_id'),\n"
        "        Index(\n"
        "            f'ix_{table_name}_zitadel_user_id_is_deleted',\n"
        "            'zitadel_user_id',\n"
        "            'is_deleted',\n"
        "        ),\n"
        "        Index(\n"
        "            f'ux_{table_name}_zitadel_user_id_name',\n"
        "            'zitadel_user_id',\n"
        "            'name',\n"
        "            unique=True,\n"
        "        ),\n"
        "    ]\n"
    )


def test_checker_accepts_one_central_standard_field_and_index_owner(tmp_path: Path) -> None:
    """Canonical factories, base delegation, indexes, and API subset pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "backend/api/resource.py": ("PRODUCT_API_MANAGED_FIELD_NAME_SET = frozenset({'id', 'is_deleted'})\n"),
            "lib/model_sqlalchemy/base.py": (
                "from lib.model_sqlalchemy.table import model_table_arg_list_get\n\n"
                "class ProductOrmBase(OrmBase):\n"
                "    def __table_cls__(cls, table_name):\n"
                "        return model_table_arg_list_get(table_name)\n"
            ),
            "lib/model_sqlalchemy/field.py": _standard_field_source_get(),
            "lib/model_sqlalchemy/table.py": _standard_table_source_get(),
            "model_sqlalchemy/app/item.py": (
                "from lib.model_sqlalchemy.base import ProductOrmBase\n"
                "from lib.model_sqlalchemy.field import (\n"
                "    model_id_column_get,\n"
                "    model_is_deleted_column_get,\n"
                "    model_name_column_get,\n"
                "    model_t_create_column_get,\n"
                "    model_t_update_column_get,\n"
                "    model_zitadel_user_id_column_get,\n"
                ")\n\n"
                "class Item(ProductOrmBase):\n"
                "    __tablename__ = 'item'\n"
                "    id: Mapped[str] = model_id_column_get()\n"
                "    is_deleted: Mapped[bool] = model_is_deleted_column_get()\n"
                "    name: Mapped[str] = model_name_column_get()\n"
                "    t_create: Mapped[datetime] = model_t_create_column_get()\n"
                "    t_update: Mapped[datetime] = model_t_update_column_get()\n"
                "    zitadel_user_id: Mapped[str] = model_zitadel_user_id_column_get()\n"
            ),
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_decentralized_fields_indexes_lifecycle_and_api_set(tmp_path: Path) -> None:
    """Every critical standard owner bypass produces one precise finding.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "backend/api/resource.py": (
                "_STANDARD_FIELD_NAME_SET = {'id'}\n" "PRODUCT_API_MANAGED_FIELD_NAME_SET = frozenset({'id', 'name'})\n"
            ),
            "lib/model_sqlalchemy/base.py": ("class ProductOrmBase(OrmBase):\n" "    pass\n"),
            "lib/model_sqlalchemy/field.py": _standard_field_source_get(),
            "lib/model_sqlalchemy/table.py": ("def model_table_arg_list_get(table_name):\n" "    return []\n"),
            "model_sqlalchemy/app/item.py": (
                "from lib.model_sqlalchemy.field import (\n"
                "    model_is_deleted_column_get,\n"
                "    model_t_create_column_get,\n"
                "    model_t_update_column_get,\n"
                ")\n\n"
                "class Item(OrmBase):\n"
                "    __tablename__ = 'item'\n"
                "    id: Mapped[str] = mapped_column()\n"
                "    is_deleted: Mapped[bool] = model_is_deleted_column_get()\n"
                "    t_create: Mapped[datetime] = model_t_create_column_get(default_factory=True)\n"
                "    t_update: Mapped[datetime] = model_t_update_column_get()\n\n"
                "    __table_args__ = (\n"
                "        Index('ix_item_id', 'id'),\n"
                "        model_table_arg_list_get(table_name='item'),\n"
                "    )\n"
            ),
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    message_text = "\n".join(finding["message"] for finding in finding_list)
    assert "backend must not copy the project standard field set" in message_text
    assert "strict standard-field subset excluding name and description" in message_text
    assert "shared project ORM base must delegate standard table arguments" in message_text
    assert "standard table helper is missing index signature" in message_text
    assert "root row model must inherit the shared project ORM base" in message_text
    assert "Item.id must use model_id_column_get" in message_text
    assert "mutable lifecycle timestamps must be synchronized" in message_text
    assert "standard-only index ['id'] must use the shared table contract" in message_text
    assert "row-local standard table-argument generation is forbidden" in message_text
    assert {finding["path"] for finding in finding_list} == {
        "backend/api/resource.py",
        "lib/model_sqlalchemy/base.py",
        "lib/model_sqlalchemy/table.py",
        "model_sqlalchemy/app/item.py",
    }
    assert all(finding["line"] >= 1 for finding in finding_list)
    assert result.stderr == ""
