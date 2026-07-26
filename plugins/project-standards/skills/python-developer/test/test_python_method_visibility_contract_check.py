"""Behavior tests for provider-owned Python method-visibility checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_method_visibility_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_by_source_map: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the real method-visibility checker against synthetic modules.

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


def test_checker_accepts_external_constructor_inherited_and_framework_method_uses(tmp_path: Path) -> None:
    """External calls and explicitly fixed method shapes remain public.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/demo/source.py": (
                '"""Synthetic source."""\n\n'
                "class Base:\n"
                "    def run(self) -> None:\n"
                "        return None\n\n"
                "class Demo(Base):\n"
                "    @classmethod\n"
                '    def from_text(cls, value: str) -> "Demo":\n'
                "        return cls()\n"
            ),
            "script/use/main.py": (
                '"""Synthetic use."""\n\n'
                "from lib.demo.source import Demo\n\n"
                "Demo().run()\n"
                "VALUE = Demo.from_text('x')\n"
            ),
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_public_method_without_external_use_and_private_cross_class_use(tmp_path: Path) -> None:
    """Demotion and promotion findings identify definitions and real use sites.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/demo/source.py": (
                '"""Synthetic source."""\n\n'
                "class Demo:\n"
                "    def public_local(self) -> None:\n"
                "        return None\n\n"
                "    def _shared(self) -> None:\n"
                "        return None\n\n"
                "    def use_local(self) -> None:\n"
                "        self.public_local()\n\n"
                "class Consumer:\n"
                "    def run(self, demo: Demo) -> None:\n"
                "        demo._shared()\n"
            ),
            "script/use/main.py": (
                '"""Synthetic use."""\n\n' "from lib.demo.source import Consumer, Demo\n\n" "Consumer().run(Demo())\n"
            ),
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert any(
        finding["path"] == "lib/demo/source.py"
        and finding["line"] == 4
        and "public method Demo.public_local" in finding["message"]
        for finding in finding_list
    )
    assert any(
        finding["path"] == "lib/demo/source.py"
        and finding["line"] == 7
        and "private method Demo._shared is used outside its class" in finding["message"]
        for finding in finding_list
    )
    assert result.stderr == ""
