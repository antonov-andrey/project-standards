"""Behavior tests for provider-owned method-binding checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_method_binding_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run the real method-binding checker against synthetic Python.

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


def test_checker_reports_receiverless_helpers_invalid_classmethods_and_hardcoded_dispatch(tmp_path: Path) -> None:
    """Static, class, instance, and hardcoded-dispatch violations all report.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "class Demo:\n"
            "    @staticmethod\n"
            "    def _helper(value: str) -> str:\n"
            "        return value\n\n"
            "    @classmethod\n"
            "    def _utility(cls, value: str) -> str:\n"
            "        return value\n\n"
            "    @classmethod\n"
            "    def build(cls) -> str:\n"
            "        return 'x'\n\n"
            "    def detached(self, value: str) -> str:\n"
            "        return value\n\n"
            "    def target(self) -> None:\n"
            "        return None\n\n"
            "    def dispatch(self) -> None:\n"
            "        Demo.target(self)\n"
        ),
    )

    assert result.returncode == 1
    message_text = "\n".join(json.loads(line)["message"] for line in result.stdout.splitlines())
    assert "forbidden private @staticmethod" in message_text
    assert "forbidden private @classmethod without direct return cls" in message_text
    assert "receiverless @classmethod logic" in message_text
    assert "forbidden @classmethod outside one alternative constructor" in message_text
    assert "receiverless instance logic" in message_text
    assert "hardcoded Demo.target() instead of self.target()" in message_text
    assert result.stderr == ""


def test_checker_allows_alternative_constructors_framework_shapes_and_receiver_use(tmp_path: Path) -> None:
    """Alternative constructors and externally fixed receiver shapes pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "class OrmBase:\n"
            "    pass\n\n"
            "class ProductOrmBase(OrmBase):\n"
            "    @classmethod\n"
            "    def __table_cls__(cls):\n"
            "        return cls\n\n"
            "    @classmethod\n"
            "    def orm_constructor_kwargs_validate(cls, kwargs: dict[str, object]):\n"
            "        return kwargs\n\n"
            "class Demo:\n"
            "    @classmethod\n"
            "    def from_text(cls, value: str):\n"
            "        return cls(value)\n\n"
            "    def __init__(self, value: str):\n"
            "        self.value = value\n\n"
            "class Visitor:\n"
            "    def visit_Name(self, node):\n"
            "        return node\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
