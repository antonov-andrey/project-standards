"""Typed process contracts for project-standard checking."""

from __future__ import annotations

from pathlib import Path
from typing import NotRequired, TypedDict


class ProjectStandardCheckerConfig(TypedDict):
    """Store one normalized provider or submodule checker declaration."""

    id: str
    owner: str
    owner_repository_path: str
    owner_root: Path
    path_exclude_glob_list: list[str]
    path_include_glob_list: list[str]
    scope_strategy: str
    script_path: Path
    trigger_path_exclude_glob_list: list[str]
    trigger_path_include_glob_list: list[str]


class ProjectStandardCheckerFinding(TypedDict):
    """Store one checker-owned finding before trusted owner enrichment."""

    line: NotRequired[int]
    message: str
    path: str


class ProjectStandardExecutionError(TypedDict):
    """Store one deterministic runner, manifest, or checker error."""

    id: str
    message: str
    owner: str


class ProjectStandardFinding(TypedDict):
    """Store one validated finding enriched with its trusted checker identity."""

    id: str
    line: NotRequired[int]
    message: str
    owner: str
    path: str


class ProjectStandardPropertyDescriptor(TypedDict):
    """Store one class-level property descriptor."""

    getter_name: str | None
    line: int
    name: str


class ProjectStandardPropertyResolution(TypedDict):
    """Store module-local property factory resolution state."""

    builtins_module_name_set: set[str]
    property_factory_name_set: set[str]


class ProjectStandardPythonMethodDefinition(TypedDict):
    """Store one top-level class method definition."""

    class_base_name_set: set[str]
    class_fqn: str
    class_name: str
    decorator_name_set: set[str]
    line: int
    method_name: str
    path: str
    return_annotation_name: str | None


class ProjectStandardPythonMethodUse(TypedDict):
    """Store one resolved repository-local method use site."""

    line: int
    owner_class_fqn: str | None
    path: str


class ProjectStandardPythonSymbolDefinition(TypedDict):
    """Store one top-level Python class or function definition."""

    kind: str
    line: int
    module_name: str
    name: str
    path: str


class ProjectStandardRequest(TypedDict):
    """Store the exact version-one checker process request."""

    path_list: list[str]
    project_root: str
    protocol_version: int
    scope: str


class ProjectStandardScriptLaunchConfig(TypedDict):
    """Store one direct Python script launch boundary."""

    command_path: str
    project_root: Path
    working_root: Path


class ProjectStandardSessionOpeningAliasState(TypedDict):
    """Store statically resolved SQLAlchemy session-opening aliases."""

    direct_opener_name_set: set[str]
    project_session_module_alias_set: set[str]
    sqlalchemy_config_alias_set: set[str]
    sqlalchemy_module_alias_set: set[str]


class ProjectStandardValidatedConstructorPrevalidation(TypedDict):
    """Store one validated constructor call with hidden pre-validation."""

    line: int
    target_fqn: str


class ProjectStandardValidatedFieldWrapper(TypedDict):
    """Store one accessor wrapper around canonical validated field state."""

    field_name: str
    kind: str
    line: int
    name: str
