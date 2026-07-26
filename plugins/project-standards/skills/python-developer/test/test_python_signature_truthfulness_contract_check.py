"""Behavior tests for provider-owned signature-truthfulness checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_signature_truthfulness_contract_check.py"
)
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run the real truthfulness checker against synthetic Python.

    Args:
        project_root: Synthetic Git repository root.
        source: Python source under test.

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


def test_checker_reports_abstract_and_concrete_collection_mismatches(tmp_path: Path) -> None:
    """Every abstract-interface and clearly narrower-concrete branch reports.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "from collections.abc import Collection, Iterable, Mapping, Sequence\n\n"
            "def inspect_iterable(item_iterable: Iterable[str]):\n"
            "    return len(item_iterable)\n\n"
            "def inspect_collection(item_collection: Collection[str]):\n"
            "    return item_collection[0]\n\n"
            "def mutate_sequence(item_list: Sequence[str]):\n"
            "    item_list.append('x')\n\n"
            "def mutate_mapping(item_by_id_map: Mapping[str, str]):\n"
            "    item_by_id_map.update({'x': 'y'})\n\n"
            "def inspect_list(item_list: list[str]):\n"
            "    return item_list[0]\n\n"
            "def inspect_dict(item_by_id_map: dict[str, str]):\n"
            "    return item_by_id_map.get('x')\n"
        ),
    )

    assert result.returncode == 1
    message_text = "\n".join(json.loads(line)["message"] for line in result.stdout.splitlines())
    assert "Iterable uses operations outside iteration-only contract" in message_text
    assert "Collection uses operations outside membership/length contract" in message_text
    assert "Sequence uses operations outside ordered read-only contract" in message_text
    assert "Mapping uses operations outside read-only key/value contract" in message_text
    assert "list uses only ordered read-only sequence operations" in message_text
    assert "dict uses only read-only mapping operations" in message_text
    assert result.stderr == ""


def test_checker_reports_broad_and_string_path_contracts_but_allows_normalization(tmp_path: Path) -> None:
    """Broad shape hiding and direct string paths fail while explicit narrowing passes.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "from pathlib import Path\n"
            "from typing import Any\n\n"
            "def broad_collection(item: Any):\n"
            "    return item[0]\n\n"
            "def broad_path(path: object):\n"
            "    return Path(path)\n\n"
            "def raw_path(path: str):\n"
            "    return path.read_text()\n\n"
            "def normalized_path(path: str):\n"
            "    normalized_path = Path(path)\n"
            "    return normalized_path.read_text()\n\n"
            "def branched(value: object):\n"
            "    return value[0] if isinstance(value, list) else None\n"
        ),
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    message_text = "\n".join(finding["message"] for finding in finding_list)
    assert "Any uses one collection-specific runtime contract" in message_text
    assert "object uses one path-specific runtime contract" in message_text
    assert "str uses path operations before one boundary normalization to Path" in message_text
    assert len(finding_list) == 3
    assert result.stderr == ""


def test_checker_allows_mutable_concrete_collections_and_matching_abstract_interfaces(tmp_path: Path) -> None:
    """Concrete mutation and correctly restricted abstract operations pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "from collections.abc import Collection, Iterable, Mapping, Sequence\n\n"
            "def consume(item_iterable: Iterable[str], item_collection: Collection[str]):\n"
            "    return [item for item in item_iterable if item in item_collection]\n\n"
            "def read(item_list: Sequence[str], item_by_id_map: Mapping[str, str]):\n"
            "    return item_list[0], item_by_id_map.get('x')\n\n"
            "def mutate(item_list: list[str], item_by_id_map: dict[str, str]):\n"
            "    item_list.append('x')\n"
            "    item_by_id_map['x'] = 'y'\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
