"""Behavior tests for the static row ORM model checker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "orm_model_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_list: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the real checker process against one synthetic repository.

    Args:
        project_root: Exact synthetic repository root.
        relative_path_list: Current repository-relative path list.

    Returns:
        Completed checker process.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], check=True, cwd=project_root)
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


def test_checker_accepts_canonical_typed_row_fields_and_alternative_constructor(tmp_path: Path) -> None:
    """One canonical row declaration satisfies every static model branch.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    model_path = project_root / "model_sqlalchemy" / "app" / "item.py"
    model_path.parent.mkdir(parents=True)
    model_path.write_text(
        (
            "from sqlalchemy.orm import Mapped, mapped_column\n\n"
            "class Item(OrmBase):\n"
            "    __orm_validation_enabled__ = True\n"
            '    __tablename__ = "item"\n'
            "    id: Mapped[str] = mapped_column(nullable=False)\n"
            "    metadata_payload: Mapped[dict[str, str]] = mapped_column(\n"
            "        nullable=False,\n"
            "        info={'validated_object': {'default_factory': dict}},\n"
            "    )\n"
            "    value_list: Mapped[list[str]] = mapped_column(nullable=False)\n\n"
            "    @classmethod\n"
            "    def from_name(cls, name: str):\n"
            "        return cls(id=name, metadata_payload={}, value_list=[])\n"
        ),
        encoding="utf-8",
    )

    result = _checker_run(project_root, ["model_sqlalchemy/app/item.py"])

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_field_method_constraint_and_metadata_failures(tmp_path: Path) -> None:
    """Every critical static row-model failure emits one concrete diagnostic.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    model_path = project_root / "model_sqlalchemy" / "app" / "item.py"
    model_path.parent.mkdir(parents=True)
    model_path.write_text(
        (
            "from sqlalchemy import Column, ForeignKey\n"
            "from sqlalchemy.orm import Mapped, mapped_column\n\n"
            "class Item(OrmBase):\n"
            '    __tablename__ = "item"\n'
            "    z_value: Mapped[str] = mapped_column(nullable=False)\n"
            "    item: Mapped[list[str]] = mapped_column('items', nullable=False)\n"
            "    optional: Mapped[str | None] = mapped_column(nullable=False)\n"
            "    raw = Column()\n"
            "    parent = ForeignKey('item.id')\n"
            "    metadata: Mapped[dict[str, str]] = mapped_column(\n"
            "        nullable=False,\n"
            "        info={'validated_object': {'python_type': dict}},\n"
            "    )\n\n"
            "    @staticmethod\n"
            "    def helper():\n"
            "        return None\n\n"
            "    @classmethod\n"
            "    def build(cls):\n"
            "        return object()\n"
        ),
        encoding="utf-8",
    )

    result = _checker_run(project_root, ["model_sqlalchemy/app/item.py"])

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    message_set = {finding["message"] for finding in finding_list}
    assert "legacy Column(...) declarations are forbidden" in message_set
    assert "ForeignKey constraints are forbidden in governed ORM models" in message_set
    assert "Item must declare __orm_validation_enabled__ = True" in message_set
    assert (
        "mapped column declarations must be alphabetical: found ['z_value', 'item', 'optional', 'metadata']"
        in message_set
    )
    assert "field item annotated as list[...] must end with _list" in message_set
    assert "backing column items for item annotated as list[...] must end with _list" in message_set
    assert "Item.optional annotation nullability does not match mapped_column(nullable=False)" in message_set
    assert "unsupported validated_object keys: ['python_type']" in message_set
    assert "Item.helper must not be a staticmethod" in message_set
    assert "Item.build is not one valid alternative constructor" in message_set
    assert all(finding["path"] == "model_sqlalchemy/app/item.py" for finding in finding_list)
    assert result.stderr == ""


def test_checker_reports_inherited_wrapper_constructor_and_default_bypasses(tmp_path: Path) -> None:
    """Inherited fields and every validation-sensitive default branch report.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    base_path = project_root / "model_sqlalchemy" / "app" / "base.py"
    item_path = project_root / "model_sqlalchemy" / "app" / "item.py"
    service_path = project_root / "backend" / "service.py"
    base_path.parent.mkdir(parents=True)
    service_path.parent.mkdir(parents=True)
    base_path.write_text(
        (
            "from sqlalchemy.orm import Mapped, mapped_column\n\n"
            "class SharedRow(OrmBase):\n"
            "    __abstract__ = True\n"
            "    inherited: Mapped[str] = mapped_column(nullable=False)\n"
        ),
        encoding="utf-8",
    )
    item_path.write_text(
        (
            "from builtins import property as property_alias\n"
            "from sqlalchemy.orm import Mapped, mapped_column\n"
            "from model_sqlalchemy.app.base import SharedRow\n\n"
            "class Item(SharedRow):\n"
            "    __orm_validation_enabled__ = True\n"
            '    __tablename__ = "item"\n'
            "    id: Mapped[str] = mapped_column(nullable=False)\n"
            "    payload_list: Mapped[list[str]] = mapped_column(\n"
            "        nullable=False,\n"
            "        default=[],\n"
            "        info={'validated_object': {'default_factory': lambda seed: [seed]}},\n"
            "    )\n"
            "    raw = mapped_column(nullable=False)\n"
            "    __table_args__ = ()\n\n"
            "    def __init__(self, **value_by_name_map):\n"
            "        super().__init__(**value_by_name_map)\n\n"
            "    def inherited_get(self):\n"
            "        return self.inherited\n\n"
            "    inherited_alias = property_alias(inherited_get)\n\n"
            "    def model_copy(self):\n"
            "        return self\n"
        ),
        encoding="utf-8",
    )
    service_path.write_text(
        ("from model_sqlalchemy.app.item import Item\n\n" "ITEM = Item(id=int('1'), inherited='x', payload_list=[])\n"),
        encoding="utf-8",
    )

    result = _checker_run(
        project_root,
        [
            "backend/service.py",
            "model_sqlalchemy/app/base.py",
            "model_sqlalchemy/app/item.py",
        ],
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    message_text = "\n".join(finding["message"] for finding in finding_list)
    assert "constructor receives hidden coercion" in message_text
    assert "Item mapped fields must use Mapped[...] annotated assignments" in message_text
    assert "Item.payload_list default must be one scalar literal" in message_text
    assert "validated_object default_factory must be no-arg invocable" in message_text
    assert "system class attribute __table_args__ must precede ORM fields" in message_text
    assert "Item overrides validation-sensitive __init__" in message_text
    assert "Item overrides validation-sensitive model_copy" in message_text
    assert "wraps ORM field inherited" in message_text
    assert {finding["path"] for finding in finding_list} == {
        "backend/service.py",
        "model_sqlalchemy/app/item.py",
    }
    assert result.stderr == ""
