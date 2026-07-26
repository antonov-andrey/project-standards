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


class ProjectStandardRequest(TypedDict):
    """Store the exact version-one checker process request."""

    path_list: list[str]
    project_root: str
    protocol_version: int
    scope: str
