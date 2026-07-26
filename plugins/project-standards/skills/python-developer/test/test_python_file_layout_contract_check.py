"""Behavior tests for provider-owned Python file-layout checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_file_layout_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, source: str) -> subprocess.CompletedProcess[str]:
    """Run the real file-layout checker against synthetic Python.

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


def test_checker_reports_import_top_level_block_and_helper_placement_errors(tmp_path: Path) -> None:
    """Import groups, item blocks, alphabetical order, and helper placement report.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "from package import zebra, alpha\n"
            "import os\n\n"
            "VALUE_B = 2\n\n"
            "VALUE_A = 1\n\n"
            "def public_b():\n"
            "    return _helper()\n\n"
            "def public_a():\n"
            "    return None\n\n"
            "def _helper():\n"
            "    return VALUE_A\n\n"
            "class Zebra:\n"
            "    pass\n\n"
            "class Alpha:\n"
            "    pass\n"
        ),
    )

    assert result.returncode == 1
    message_text = "\n".join(json.loads(line)["message"] for line in result.stdout.splitlines())
    assert "import groups are not ordered" in message_text
    assert "imported names inside one from-import statement must be sorted" in message_text
    assert "constant items must follow dependency-aware alphabetical order" in message_text
    assert "public function items must follow dependency-aware alphabetical order" in message_text
    assert "class block items must follow dependency-aware alphabetical order" in message_text
    assert "private helper block before public_b" in message_text
    assert result.stderr == ""


def test_checker_allows_dependency_order_and_canonical_private_helper_block(tmp_path: Path) -> None:
    """Eager dependencies and a helper immediately before its consumer pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "import os\n"
            "from pathlib import Path\n\n"
            "BASE = Path('.')\n"
            "DERIVED = BASE / 'data'\n\n"
            "runtime_path = DERIVED\n\n"
            "def _helper() -> str:\n"
            "    return os.fspath(runtime_path)\n\n"
            "def public() -> str:\n"
            "    return _helper()\n\n"
            "class Owner:\n"
            "    pass\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
