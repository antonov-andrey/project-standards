"""Behavior tests for the provider-owned Python script contract checker."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "python_script_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_list: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the real checker process against one synthetic repository.

    Args:
        project_root: Exact synthetic repository root.
        relative_path_list: Current repository-relative path list.

    Returns:
        Completed checker process.
    """

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PACKAGE_ROOT)
    return subprocess.run(
        [sys.executable, str(CHECKER_PATH)],
        capture_output=True,
        check=False,
        cwd=project_root,
        env=environment,
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


def _git_init(project_root: Path) -> None:
    """Initialize one synthetic Git worktree.

    Args:
        project_root: Directory to initialize.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], check=True, cwd=project_root)


def _script_write(path: Path, source: str, *, mode: int = 0o755) -> None:
    """Create one executable Python script fixture.

    Args:
        path: Script path to create.
        source: Python source below the shebang.
        mode: Resulting filesystem mode.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/usr/bin/env python3\n{source}", encoding="utf-8")
    path.chmod(mode)


def test_checker_accepts_root_skill_and_portable_submodule_scripts(tmp_path: Path) -> None:
    """Canonical scripts launch from every required owning boundary.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    project_root.mkdir()
    _git_init(project_root)
    _script_write(
        project_root / "tool" / "root_tool.py",
        (
            "import argparse\n"
            "import black\n"
            "try:\n"
            "    raise TypeError\n"
            "except TypeError, ValueError:\n"
            "    pass\n"
            'if __name__ == "__main__":\n'
            "    argparse.ArgumentParser(description='Root tool.').parse_args()\n"
        ),
    )
    skill_root = project_root / "plugins" / "demo" / "skills" / "sample"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# Sample\n", encoding="utf-8")
    _script_write(
        skill_root / "scripts" / "skill_tool.py",
        (
            "import argparse\n"
            'if __name__ == "__main__":\n'
            "    argparse.ArgumentParser(description='Skill tool.').parse_args()\n"
        ),
    )
    submodule_root = project_root / "provider"
    submodule_root.mkdir()
    _git_init(submodule_root)
    _script_write(
        submodule_root / "tool" / "provider_tool.py",
        (
            "import argparse\n"
            'if __name__ == "__main__":\n'
            "    argparse.ArgumentParser(description='Provider tool.').parse_args()\n"
        ),
    )
    (project_root / ".gitmodules").write_text(
        '[submodule "provider"]\n\tpath = provider\n\turl = https://example.invalid/provider.git\n',
        encoding="utf-8",
    )
    relative_path_list = [
        ".gitmodules",
        "plugins/demo/skills/sample/SKILL.md",
        "plugins/demo/skills/sample/scripts/skill_tool.py",
        "provider/tool/provider_tool.py",
        "tool/root_tool.py",
    ]

    result = _checker_run(project_root, relative_path_list)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_shell_unexpected_guard_and_help_shortcuts(tmp_path: Path) -> None:
    """Every primary root script artifact failure reports path and line.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    project_root.mkdir()
    _git_init(project_root)
    shell_path = project_root / "legacy.sh"
    shell_path.write_text("#!/bin/sh\n", encoding="utf-8")
    module_path = project_root / "lib" / "module.py"
    module_path.parent.mkdir()
    module_path.write_text('if __name__ == "__main__":\n    pass\n', encoding="utf-8")
    script_path = project_root / "tool" / "broken.py"
    _script_write(
        script_path,
        (
            "import argparse\n"
            "import sys\n"
            "if '--help' in sys.argv:\n"
            "    raise SystemExit(0)\n"
            "parser = argparse.ArgumentParser(add_help=False)\n"
            "parser.add_argument('-h', '--help', action='store_true')\n"
            'if __name__ == "__main__":\n'
            "    parser.parse_args()\n"
        ),
        mode=0o644,
    )

    result = _checker_run(
        project_root,
        ["legacy.sh", "lib/module.py", "tool/broken.py"],
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert {finding["path"] for finding in finding_list} == {
        "legacy.sh",
        "lib/module.py",
        "tool/broken.py",
    }
    assert {
        (finding.get("line"), finding["message"]) for finding in finding_list if finding["path"] == "tool/broken.py"
    } >= {
        (4, "--help must use the standard parser path, not an explicit help shortcut"),
        (6, "--help must use the standard parser path, not ArgumentParser(add_help=False)"),
        (7, "--help must use the standard parser path, not a manual help argument"),
        (None, "expected executable mode 755, found 644"),
    }
    assert result.stderr == ""


def test_checker_reports_submodule_import_escape(tmp_path: Path) -> None:
    """A submodule script cannot import consumer-only repository code.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    project_root.mkdir()
    _git_init(project_root)
    consumer_package = project_root / "consumer_package"
    consumer_package.mkdir()
    (consumer_package / "__init__.py").write_text("", encoding="utf-8")
    submodule_root = project_root / "provider"
    submodule_root.mkdir()
    _git_init(submodule_root)
    _script_write(
        submodule_root / "tool" / "provider_tool.py",
        (
            "import argparse\n"
            "import consumer_package\n"
            'if __name__ == "__main__":\n'
            "    argparse.ArgumentParser(description='Provider tool.').parse_args()\n"
        ),
    )
    (project_root / ".gitmodules").write_text(
        '[submodule "provider"]\n\tpath = provider\n\turl = https://example.invalid/provider.git\n',
        encoding="utf-8",
    )

    result = _checker_run(
        project_root,
        [
            ".gitmodules",
            "consumer_package/__init__.py",
            "provider/tool/provider_tool.py",
        ],
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert {
        "message": "script imports consumer code outside its owning submodule: consumer_package",
        "path": "provider/tool/provider_tool.py",
    } in finding_list
