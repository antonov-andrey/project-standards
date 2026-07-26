"""Behavior tests for provider-owned Python naming and carrier checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_naming_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run the real checker against one synthetic repository.

    Args:
        project_root: Synthetic Git repository root.
        source: Python source to check.

    Returns:
        Completed checker process.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project_root, check=True)
    (project_root / "module.py").write_text(source, encoding="utf-8")
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
                "path_list": ["module.py"],
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_accepts_canonical_names_and_boundary_dicts(tmp_path: Path) -> None:
    """Canonical carrier, temporal, bool, and JSON-boundary names pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Describe the module."""\n\n'
            "from datetime import datetime\n\n"
            "def is_item_ready(\n"
            "    item_list: list[str], payload: dict[str, object], t_create: datetime, t_update_offer_count: datetime\n"
            ") -> bool:\n"
            '    """Return whether items are ready."""\n'
            "    value_by_key_map: dict[str, str] = {}\n"
            "    seen_set: set[str] = set()\n"
            "    return bool(item_list or payload or t_create or t_update_offer_count or value_by_key_map or seen_set)\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_typed_name_and_callable_shape_mismatches(tmp_path: Path) -> None:
    """Primary temporal, numeric, carrier, map, and bool mismatches report.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Describe the module."""\n\n'
            "def items_get(items: list[str], t_create: str, item_count: str) -> bool:\n"
            '    """Return one invalid carrier."""\n'
            "    mapping: dict[str, str] = {}\n"
            "    values: set[str] = set()\n"
            "    return bool(items or t_create or item_count or mapping or values)\n"
        ),
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    message_text = "\n".join(finding["message"] for finding in finding_list)
    assert "returning bool must use one canonical boolean prefix" in message_text
    assert "list-like name items must end with _list" in message_text
    assert "temporal name t_create must use datetime" in message_text
    assert "item_count ending with _count must use int" in message_text
    assert "dict-like name mapping must use the form value_by_key_map" in message_text
    assert "set name values must end with _set" in message_text
    assert all(finding["path"] == "module.py" and finding["line"] == 3 for finding in finding_list)
    assert result.stderr == ""
