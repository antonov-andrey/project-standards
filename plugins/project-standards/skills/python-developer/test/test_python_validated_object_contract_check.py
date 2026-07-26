"""Behavior tests for provider-owned validated-object checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_validated_object_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_by_source_map: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the real validated-object checker against synthetic modules.

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


def test_checker_accepts_ordered_direct_fields_behavior_class_and_raw_constructor_values(tmp_path: Path) -> None:
    """Canonical fields and behavior-only classes pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "model.py": (
                '"""Synthetic models."""\n\n'
                "from typing import TypedDict\n\n"
                "from base_model import BaseModelStrict\n\n"
                "class BoundaryPayload(TypedDict):\n"
                "    name: str\n\n"
                "class Demo(BaseModelStrict):\n"
                "    model_config = {}\n"
                "    name: str\n"
                "    value: int\n\n"
                "class Runner:\n"
                "    def run(self, value: int) -> int:\n"
                "        return value + 1\n\n"
                "ITEM = Demo(name='x', value=1)\n"
            )
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_constructor_bypass_field_order_wrapper_and_plain_data_contract(tmp_path: Path) -> None:
    """Critical constructor, field, accessor, and plain-data branches report.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "model.py": (
                '"""Synthetic models."""\n\n'
                "from base_model import BaseModelStrict\n\n"
                "class Demo(BaseModelStrict):\n"
                "    value: int\n"
                "    name: str\n"
                "    model_config = {}\n\n"
                "    def value_get(self) -> int:\n"
                "        return self.value\n\n"
                "class Plain:\n"
                "    def __init__(self, value: int) -> None:\n"
                "        self.value = value\n\n"
                "ITEM = Demo(value=int('1'), name='x')\n"
                "BROKEN = Demo.model_construct(value=1, name='x')\n"
            )
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert {finding["path"] for finding in finding_list} == {"model.py"}
    message_text = "\n".join(finding["message"] for finding in finding_list)
    assert "fields are not alphabetical" in message_text
    assert "system class attribute model_config must precede validated fields" in message_text
    assert "wraps canonical field value" in message_text
    assert "plain class model.Plain exposes instance field value" in message_text
    assert "constructor receives hidden coercion" in message_text
    assert "model_construct() bypasses validated-object construction" in message_text
    assert result.stderr == ""
