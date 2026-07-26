"""Behavior tests for provider-owned Python import checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_import_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(
    project_root: Path,
    source_by_relative_path_map: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run the real import checker against one synthetic repository.

    Args:
        project_root: Synthetic Git repository root.
        source_by_relative_path_map: Python source keyed by repository path.

    Returns:
        Completed checker process.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project_root, check=True)
    for relative_path, source in source_by_relative_path_map.items():
        path = project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    relative_path_list = sorted(source_by_relative_path_map)
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
                "path_list": relative_path_list,
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_reports_private_cross_module_access_aliases_fallback_and_nested_import(tmp_path: Path) -> None:
    """Visibility, fallback, alias, and non-module import branches report.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/__init__.py": '"""Package."""\n',
            "lib/owner.py": '"""Owner."""\n\n_private = 1\n',
            "lib/user.py": (
                '"""User."""\n\n'
                "import lib.owner as _owner\n"
                "from lib.owner import _private\n"
                "import lib.owner as owner\n\n"
                "try:\n"
                "    import missing\n"
                "except ImportError:\n"
                "    missing = None\n\n"
                "public = _private\n"
                "other = owner._private\n\n"
                "def run():\n"
                "    import os\n"
                "    return _owner, other, os\n"
            ),
        },
    )

    assert result.returncode == 1
    message_text = "\n".join(json.loads(line)["message"] for line in result.stdout.splitlines())
    assert "private import alias _owner" in message_text
    assert "private from-import _private" in message_text
    assert "import fallback try/except" in message_text
    assert "public alias public assigned from private name _private" in message_text
    assert "public alias other assigned from private attribute owner._private" in message_text
    assert "private attribute access owner._private" in message_text
    assert "non-module import inside run" in message_text
    assert result.stderr == ""


def test_checker_reports_legacy_dependency_and_repository_cycle(tmp_path: Path) -> None:
    """Legacy dependency and deterministic local import cycle both report.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "legacy/__init__.py": '"""Legacy package."""\n',
            "legacy/old.py": '"""Legacy module."""\n',
            "lib/a.py": '"""A."""\n\nimport lib.b\nimport legacy.old\n',
            "lib/b.py": '"""B."""\n\nimport lib.a\n',
        },
    )

    assert result.returncode == 1
    message_text = "\n".join(json.loads(line)["message"] for line in result.stdout.splitlines())
    assert "forbidden import of Legacy module legacy.old" in message_text
    assert "repository-local import cycle: lib.a -> lib.b -> lib.a" in message_text
    assert result.stderr == ""


def test_checker_allows_module_imports_and_lazy_package_getattr(tmp_path: Path) -> None:
    """Public module-scope imports and package lazy export imports pass.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/__init__.py": (
                '"""Package."""\n\n'
                "def __getattr__(name: str):\n"
                "    from lib.owner import Public\n"
                "    return Public if name == 'Public' else None\n"
            ),
            "lib/owner.py": '"""Owner."""\n\nclass Public:\n    pass\n',
            "lib/user.py": '"""User."""\n\nfrom lib.owner import Public\n\nvalue = Public()\n',
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
