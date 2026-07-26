"""Behavior tests for owner-aware repository import resolution."""

from __future__ import annotations

import ast

from project_standards.python_import import (
    relative_path_by_module_name_map_get,
    repository_dependency_name_set_get,
)


def test_nested_distribution_source_root_resolves_public_package_import() -> None:
    """A nested plugin distribution uses its installed package identity."""

    relative_path_list = [
        "plugins/provider/lib/provider_package/__init__.py",
        "plugins/provider/lib/provider_package/client.py",
        "plugins/provider/lib/provider_package/runtime.py",
    ]
    relative_path_by_module_name_map = relative_path_by_module_name_map_get(relative_path_list)

    assert relative_path_by_module_name_map["provider_package"] == relative_path_list[0]
    assert relative_path_by_module_name_map["provider_package.client"] == relative_path_list[1]
    assert repository_dependency_name_set_get(
        relative_path_list[2],
        ast.parse("from provider_package.client import Client\n"),
        relative_path_by_module_name_map,
    ) == {"plugins.provider.lib.provider_package.client"}


def test_skill_script_resolves_its_owner_local_lib_import() -> None:
    """A Skill checker links `lib.*` to its own scripts owner."""

    relative_path_list = [
        "plugins/provider/skills/sample/scripts/check.py",
        "plugins/provider/skills/sample/scripts/lib/runtime.py",
    ]
    relative_path_by_module_name_map = relative_path_by_module_name_map_get(relative_path_list)

    assert repository_dependency_name_set_get(
        relative_path_list[0],
        ast.parse("from lib.runtime import run\n"),
        relative_path_by_module_name_map,
    ) == {"plugins.provider.skills.sample.scripts.lib.runtime"}
