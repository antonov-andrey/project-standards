"""Behavior tests for exact checker manifests and path selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_standards import project_standard_check
from project_standards.project_standard_model import (
    ProjectStandardCheckerConfig,
    ProjectStandardExecutionError,
)

CHECKER_SOURCE = '''"""Fixture checker."""
'''


def _manifest_write(
    owner_root: Path,
    *,
    owner: str = "project-standards:python-developer",
    root_suffix: str = "",
    schema_version: int = 1,
    check_suffix: str = "",
    scope_strategy: str = "path-local",
    script_path: str = "scripts/check.py",
) -> Path:
    """Write one configurable version-one checker manifest.

    Args:
        owner_root: Directory that owns the manifest and script.
        owner: Manifest owner identity.
        root_suffix: Additional root-level TOML.
        schema_version: Manifest protocol schema version.
        check_suffix: Additional check-level TOML.
        scope_strategy: Declared checker scope strategy.
        script_path: Manifest-relative checker script path.

    Returns:
        Written manifest path.
    """

    script_root = owner_root / "scripts"
    script_root.mkdir(parents=True)
    (script_root / "check.py").write_text(CHECKER_SOURCE, encoding="utf-8")
    manifest_path = owner_root / "checker.toml"
    manifest_path.write_text(
        (
            f"schema_version = {schema_version}\n"
            f'owner = "{owner}"\n'
            f"{root_suffix}"
            "\n"
            "[[check_list]]\n"
            'id = "python.sample"\n'
            f'script_path = "{script_path}"\n'
            f'scope_strategy = "{scope_strategy}"\n'
            'path_include_glob_list = ["**/*.py", "pyproject.toml"]\n'
            'path_exclude_glob_list = ["generated/**"]\n'
            'trigger_path_include_glob_list = ["**/*.py", "AGENTS.md"]\n'
            'trigger_path_exclude_glob_list = ["vendor/**"]\n'
            f"{check_suffix}"
        ),
        encoding="utf-8",
    )
    return manifest_path


def _manifest_config_list_get(
    manifest_path: Path,
    *,
    expected_owner: str = "project-standards:python-developer",
    owner_repository_path: str = "",
) -> list[ProjectStandardCheckerConfig]:
    """Parse one fixture manifest through the production boundary.

    Args:
        manifest_path: Fixture manifest path.
        expected_owner: Trusted owner identity.
        owner_repository_path: Consumer-relative submodule path.

    Returns:
        Normalized checker declaration list.
    """

    return project_standard_check._manifest_checker_config_list_get(
        expected_owner=expected_owner,
        manifest_path=manifest_path,
        owner_repository_path=owner_repository_path,
        owner_root=manifest_path.parent,
    )


def test_manifest_accepts_exact_capability_and_submodule_version_one(tmp_path: Path) -> None:
    """Capability and submodule manifests preserve their distinct scope rules.

    Args:
        tmp_path: Pytest temporary directory.
    """

    capability_manifest_path = _manifest_write(tmp_path / "capability")
    capability_config = _manifest_config_list_get(capability_manifest_path)[0]
    assert capability_config == {
        "id": "python.sample",
        "owner": "project-standards:python-developer",
        "owner_repository_path": "",
        "owner_root": capability_manifest_path.parent.resolve(),
        "path_exclude_glob_list": ["generated/**"],
        "path_include_glob_list": ["**/*.py", "pyproject.toml"],
        "scope_strategy": "path-local",
        "script_path": (capability_manifest_path.parent / "scripts" / "check.py").resolve(),
        "trigger_path_exclude_glob_list": ["vendor/**"],
        "trigger_path_include_glob_list": ["**/*.py", "AGENTS.md"],
    }

    submodule_manifest_path = _manifest_write(
        tmp_path / "submodule",
        owner="submodule:provider",
        scope_strategy="full-on-change",
    )
    submodule_config = _manifest_config_list_get(
        submodule_manifest_path,
        expected_owner="submodule:provider",
        owner_repository_path="provider",
    )[0]
    assert submodule_config["owner_repository_path"] == "provider"
    assert submodule_config["scope_strategy"] == "full-on-change"


@pytest.mark.parametrize(
    ("manifest_change", "message"),
    [
        ({"root_suffix": 'unknown = "value"\n'}, "root fields"),
        ({"schema_version": 2}, "unsupported schema_version"),
        ({"owner": "project-standards:other"}, "does not match"),
        ({"check_suffix": 'unknown = "value"\n'}, "check has unsupported"),
        ({"script_path": "../check.py"}, "relative POSIX path"),
        ({"script_path": "scripts/missing.py"}, "owner-local file"),
    ],
)
def test_manifest_rejects_unknown_owner_schema_fields_and_escaping_script(
    tmp_path: Path,
    manifest_change: dict[str, object],
    message: str,
) -> None:
    """Untrusted manifests cannot extend schema or escape their owner.

    Args:
        tmp_path: Pytest temporary directory.
        manifest_change: Keyword override for the manifest fixture.
        message: Expected parser diagnostic fragment.
    """

    manifest_path = _manifest_write(tmp_path / "owner", **manifest_change)

    with pytest.raises(ValueError, match=message):
        _manifest_config_list_get(manifest_path)


@pytest.mark.parametrize("pattern", ["", "!generated/**", "/absolute/**", "foo\\\\"])
def test_manifest_rejects_empty_negated_absolute_and_invalid_globs(tmp_path: Path, pattern: str) -> None:
    """Every unsupported Git-wildmatch pattern shape is rejected.

    Args:
        tmp_path: Pytest temporary directory.
        pattern: Invalid manifest pattern.
    """

    manifest_path = _manifest_write(tmp_path / "owner")
    text = manifest_path.read_text(encoding="utf-8")
    text = text.replace(
        'path_include_glob_list = ["**/*.py", "pyproject.toml"]',
        f'path_include_glob_list = ["{pattern}"]',
    )
    manifest_path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="pattern|invalid|must not be empty"):
        _manifest_config_list_get(manifest_path)


def test_manifest_rejects_duplicate_id_and_path_local_submodule(tmp_path: Path) -> None:
    """Duplicate identities and path-local submodule checks are forbidden.

    Args:
        tmp_path: Pytest temporary directory.
    """

    duplicate_manifest_path = _manifest_write(tmp_path / "duplicate")
    duplicate_manifest_path.write_text(
        duplicate_manifest_path.read_text(encoding="utf-8")
        + (
            "\n[[check_list]]\n"
            'id = "python.sample"\n'
            'script_path = "scripts/check.py"\n'
            'scope_strategy = "path-local"\n'
            'path_include_glob_list = ["**/*.py"]\n'
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="repeats id"):
        _manifest_config_list_get(duplicate_manifest_path)

    submodule_manifest_path = _manifest_write(
        tmp_path / "submodule",
        owner="submodule:provider",
    )
    with pytest.raises(ValueError, match="must use full-on-change"):
        _manifest_config_list_get(
            submodule_manifest_path,
            expected_owner="submodule:provider",
            owner_repository_path="provider",
        )


def test_checker_identity_dedupe_reports_duplicate_and_keeps_other_config(tmp_path: Path) -> None:
    """Cross-manifest duplicate identities fail without hiding unique checks.

    Args:
        tmp_path: Pytest temporary directory.
    """

    manifest_path = _manifest_write(tmp_path / "owner")
    checker_config = _manifest_config_list_get(manifest_path)[0]
    other_config = ProjectStandardCheckerConfig(**checker_config)
    other_config["id"] = "python.other"
    execution_error_list: list[ProjectStandardExecutionError] = []

    result = project_standard_check._checker_config_list_dedupe(
        [checker_config, other_config, checker_config],
        execution_error_list,
    )

    assert [config["id"] for config in result] == ["python.other"]
    assert execution_error_list == [
        {
            "id": "python.sample",
            "message": "Duplicate checker identity: ('project-standards:python-developer', 'python.sample')",
            "owner": "project-standards:python-developer",
        }
    ]


def test_gitwildmatch_selection_preserves_path_local_and_full_on_change_semantics(tmp_path: Path) -> None:
    """Includes, excludes, triggers, and scope strategies select exact paths.

    Args:
        tmp_path: Pytest temporary directory.
    """

    manifest_path = _manifest_write(tmp_path / "owner")
    checker_config = _manifest_config_list_get(manifest_path)[0]
    all_path_list = ["AGENTS.md", "app.py", "generated/code.py", "nested/module.py", "pyproject.toml", "vendor/lib.py"]
    changed_path_list = ["AGENTS.md", "generated/code.py", "nested/module.py", "removed.py", "vendor/lib.py"]

    assert project_standard_check._should_checker_run(changed_path_list, checker_config, "changed")
    assert project_standard_check._checker_path_list_get(
        all_path_list,
        changed_path_list,
        checker_config,
        "changed",
        {},
    ) == ["nested/module.py", "vendor/lib.py"]
    assert not project_standard_check._should_checker_run(["vendor/lib.py"], checker_config, "changed")
    checker_config["scope_strategy"] = "full-on-change"
    assert project_standard_check._checker_path_list_get(
        all_path_list,
        changed_path_list,
        checker_config,
        "changed",
        {},
    ) == ["app.py", "nested/module.py", "pyproject.toml", "vendor/lib.py"]
    assert project_standard_check._checker_path_list_get(
        all_path_list,
        changed_path_list,
        checker_config,
        "all",
        {},
    ) == ["app.py", "nested/module.py", "pyproject.toml", "vendor/lib.py"]


def test_host_checker_sees_consumer_paths_and_runs_for_its_changed_gitlink(tmp_path: Path) -> None:
    """Host checkers exclude every submodule tree and react to owner changes.

    Args:
        tmp_path: Pytest temporary directory.
    """

    manifest_path = _manifest_write(
        tmp_path / "provider",
        owner="submodule:provider",
        scope_strategy="full-on-change",
    )
    checker_config = _manifest_config_list_get(
        manifest_path,
        expected_owner="submodule:provider",
        owner_repository_path="provider",
    )[0]
    submodule_name_by_path_map = {"other": "other", "provider": "provider"}

    assert project_standard_check._should_checker_run(["provider"], checker_config, "changed")
    assert project_standard_check._checker_path_list_get(
        ["app.py", "other/internal.py", "provider/internal.py"],
        ["provider"],
        checker_config,
        "changed",
        submodule_name_by_path_map,
    ) == ["app.py"]
