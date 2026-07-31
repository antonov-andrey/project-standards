"""Behavior tests for explicit owner-local pytest suite discovery."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from project_standards.pytest_plugin import _suite_path_list_get

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_STANDARDS_SOURCE_ROOT = PROJECT_ROOT / "plugins" / "project-standards" / "lib"


def _git_init(project_root: Path) -> None:
    """Initialize one isolated Git worktree.

    Args:
        project_root: Directory to initialize.
    """

    project_root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project_root, check=True)


def _pytest_run(project_root: Path, argument_list: list[str]) -> subprocess.CompletedProcess[str]:
    """Run pytest with the source plugin importable as a consumer dependency.

    Args:
        project_root: Exact fixture Git worktree.
        argument_list: Arguments passed after `python -m pytest`.

    Returns:
        Completed pytest process.
    """

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(PROJECT_STANDARDS_SOURCE_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "pytest", *argument_list],
        capture_output=True,
        check=False,
        cwd=project_root,
        env=environment,
        text=True,
    )


def _pytest_plugin_config_write(project_root: Path) -> None:
    """Require the explicit provider plugin in one consumer configuration.

    Args:
        project_root: Exact fixture Git worktree.
    """

    (project_root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "-p project_standards.pytest_plugin"\n',
        encoding="utf-8",
    )


def _test_module_write(test_root: Path, module_name: str) -> None:
    """Create one discoverable pytest module.

    Args:
        test_root: Owner-local test root.
        module_name: Test module filename.
    """

    test_root.mkdir(parents=True)
    (test_root / module_name).write_text("def test_fixture():\n    assert True\n", encoding="utf-8")


def test_suite_discovery_selects_root_skill_and_direct_submodule_owners(
    tmp_path: Path,
) -> None:
    """Discovery includes real owner roots and excludes unrelated nested repositories.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "consumer"
    _git_init(project_root)
    _test_module_write(project_root / "test", "test_root.py")
    skill_root = project_root / "plugins" / "consumer-plugin" / "skills" / "consumer-skill"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# Consumer Skill\n", encoding="utf-8")
    _test_module_write(skill_root / "test", "test_skill.py")

    submodule_root = project_root / "provider"
    _git_init(submodule_root)
    _test_module_write(submodule_root / "test", "test_provider.py")
    submodule_skill_root = submodule_root / "skills" / "provider-skill"
    submodule_skill_root.mkdir(parents=True)
    (submodule_skill_root / "SKILL.md").write_text("# Provider Skill\n", encoding="utf-8")
    _test_module_write(submodule_skill_root / "test", "test_provider_skill.py")
    subprocess.run(["git", "add", "."], cwd=submodule_root, check=True)

    unrelated_root = project_root / "unrelated"
    _git_init(unrelated_root)
    _test_module_write(unrelated_root / "test", "test_unrelated.py")

    (project_root / ".gitmodules").write_text(
        '[submodule "provider"]\n\tpath = provider\n\turl = https://example.invalid/provider.git\n',
        encoding="utf-8",
    )
    subprocess.run(
        [
            "git",
            "add",
            ".gitmodules",
            "plugins/consumer-plugin/skills/consumer-skill/SKILL.md",
        ],
        cwd=project_root,
        check=True,
    )

    relative_path_list = [path.relative_to(project_root).as_posix() for path in _suite_path_list_get(project_root)]

    assert relative_path_list == [
        "plugins/consumer-plugin/skills/consumer-skill/test",
        "provider/skills/provider-skill/test",
        "provider/test",
        "test",
    ]


def test_suite_discovery_uses_submodule_root_standalone(tmp_path: Path) -> None:
    """One submodule keeps its root and Skill tests when executed standalone.

    Args:
        tmp_path: Pytest temporary directory.
    """

    submodule_root = tmp_path / "provider"
    _git_init(submodule_root)
    _test_module_write(submodule_root / "test", "test_provider.py")
    skill_root = submodule_root / "skills" / "provider-skill"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# Provider Skill\n", encoding="utf-8")
    _test_module_write(skill_root / "test", "test_provider_skill.py")
    subprocess.run(["git", "add", "."], cwd=submodule_root, check=True)

    relative_path_list = [path.relative_to(submodule_root).as_posix() for path in _suite_path_list_get(submodule_root)]

    assert relative_path_list == ["skills/provider-skill/test", "test"]


def test_suite_discovery_excludes_ignored_task_and_environment_roots(
    tmp_path: Path,
) -> None:
    """Ignored task, environment, and build roots never become owner suites.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "consumer"
    _git_init(project_root)
    _test_module_write(project_root / "test", "test_root.py")
    for ignored_root_name in (
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".spec",
        ".venv",
        ".worktrees",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "tmp",
    ):
        skill_root = project_root / ignored_root_name / "skills" / "ignored"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text("# Ignored\n", encoding="utf-8")
        _test_module_write(skill_root / "test", "test_ignored.py")
    subprocess.run(["git", "add", "-f", "."], cwd=project_root, check=True)

    relative_path_list = [path.relative_to(project_root).as_posix() for path in _suite_path_list_get(project_root)]

    assert relative_path_list == ["test"]


def test_pytest_process_collects_each_owner_suite_once_in_deterministic_order(
    tmp_path: Path,
) -> None:
    """Real pytest collection includes each declared owner root exactly once.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "consumer"
    _git_init(project_root)
    _pytest_plugin_config_write(project_root)
    _test_module_write(project_root / "test", "test_root.py")
    skill_root = project_root / "plugins" / "consumer-plugin" / "skills" / "consumer-skill"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# Consumer Skill\n", encoding="utf-8")
    _test_module_write(skill_root / "test", "test_skill.py")

    submodule_root = project_root / "provider"
    _git_init(submodule_root)
    _test_module_write(submodule_root / "test", "test_provider.py")
    subprocess.run(["git", "add", "."], cwd=submodule_root, check=True)
    (project_root / ".gitmodules").write_text(
        '[submodule "provider"]\n\tpath = provider\n\turl = https://example.invalid/provider.git\n',
        encoding="utf-8",
    )
    unrelated_root = project_root / "unrelated"
    _git_init(unrelated_root)
    _test_module_write(unrelated_root / "test", "test_unrelated.py")
    subprocess.run(
        [
            "git",
            "add",
            ".gitmodules",
            "plugins/consumer-plugin/skills/consumer-skill/SKILL.md",
        ],
        cwd=project_root,
        check=True,
    )

    first_result = _pytest_run(project_root, ["--collect-only", "-q"])
    second_result = _pytest_run(project_root, ["--collect-only", "-q"])

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    first_collection_line_list = [line for line in first_result.stdout.splitlines() if "::test_" in line]
    second_collection_line_list = [line for line in second_result.stdout.splitlines() if "::test_" in line]
    assert first_collection_line_list == second_collection_line_list
    node_id_list = [line for line in first_result.stdout.splitlines() if "::test_fixture" in line]
    assert node_id_list == [
        "plugins/consumer-plugin/skills/consumer-skill/test/test_skill.py::test_fixture",
        "provider/test/test_provider.py::test_fixture",
        "test/test_root.py::test_fixture",
    ]


def test_pytest_process_honors_code_ignore_and_consumer_fixture_conftest(
    tmp_path: Path,
) -> None:
    """Explicit code-suite ignore coexists with one real consumer fixture.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "consumer"
    _git_init(project_root)
    _pytest_plugin_config_write(project_root)
    test_root = project_root / "test"
    _test_module_write(test_root, "test_regular.py")
    _test_module_write(test_root / "code", "test_contract.py")
    (project_root / "conftest.py").write_text(
        (
            '"""Consumer fixture owner."""\n'
            "\n"
            "import pytest\n"
            "\n"
            "\n"
            "@pytest.fixture\n"
            "def consumer_value():\n"
            '    return "consumer"\n'
        ),
        encoding="utf-8",
    )
    (test_root / "test_regular.py").write_text(
        ("def test_fixture(consumer_value):\n" '    assert consumer_value == "consumer"\n'),
        encoding="utf-8",
    )

    collect_result = _pytest_run(project_root, ["--collect-only", "-q", "--ignore=test/code"])
    run_result = _pytest_run(project_root, ["-q", "--ignore=test/code"])

    assert collect_result.returncode == 0, collect_result.stderr
    assert "test/test_regular.py::test_fixture" in collect_result.stdout
    assert "test/code/test_contract.py" not in collect_result.stdout
    assert run_result.returncode == 0, run_result.stderr
    assert "1 passed" in run_result.stdout


def test_pytest_configuration_fails_clearly_when_provider_plugin_is_absent(
    tmp_path: Path,
) -> None:
    """A consumer cannot silently run with its required discovery owner missing.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "consumer"
    _git_init(project_root)
    _pytest_plugin_config_write(project_root)
    _test_module_write(project_root / "test", "test_root.py")
    blocker_root = tmp_path / "blocker"
    blocker_root.mkdir()
    (blocker_root / "sitecustomize.py").write_text(
        (
            "import builtins\n"
            "\n"
            "_original_import = builtins.__import__\n"
            "\n"
            "def _blocked_import(name, *args, **kwargs):\n"
            '    if name == "project_standards" or name.startswith("project_standards."):\n'
            '        raise ModuleNotFoundError("No module named project_standards")\n'
            "    return _original_import(name, *args, **kwargs)\n"
            "\n"
            "builtins.__import__ = _blocked_import\n"
        ),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(blocker_root)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        check=False,
        cwd=project_root,
        env=environment,
        text=True,
    )

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "project_standards.pytest_plugin" in output
    assert "No module named" in output
    assert "project_standards" in output
