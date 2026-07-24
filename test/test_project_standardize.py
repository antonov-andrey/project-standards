"""Behavior tests for workspace standard discovery and validation."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = (
    ROOT / "plugins" / "project-standards" / "skills" / "project-standardize" / "scripts" / "project_standardize.py"
)


def _project_create(workspace_root: Path, name: str, file_by_path_map: dict[str, str]) -> Path:
    """Create one isolated Git worktree with supplied project files.

    Args:
        workspace_root: Parent workspace used by the tool.
        name: Repository directory name.
        file_by_path_map: Text content keyed by repository-relative path.

    Returns:
        Created repository root.
    """

    project_path = workspace_root / name
    project_path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], check=True, cwd=project_path)
    for relative_path, content in file_by_path_map.items():
        path = project_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return project_path


def _tool_run(workspace_root: Path, *argument_list: str) -> subprocess.CompletedProcess[str]:
    """Run project-standardize against one temporary workspace.

    Args:
        workspace_root: Explicit workspace passed to the tool.
        argument_list: Additional CLI arguments.

    Returns:
        Completed tool process.
    """

    return subprocess.run(
        [str(TOOL_PATH), "--workspace-root", str(workspace_root), *argument_list],
        capture_output=True,
        check=False,
        cwd=ROOT,
        text=True,
    )


def test_check_classifies_current_project_boundaries(tmp_path: Path) -> None:
    """Classification selects independently applicable capability standards.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _project_create(
        workspace_root,
        "application",
        {
            ".gitmodules": "",
            "AGENTS.md": "# Repository Guidelines\n",
            "DESIGN.md": "# Design\n",
            "app.py": (
                "#!/usr/bin/env python3\n"
                "import argparse\n"
                "import logging\n"
                "import os\n"
                "import requests\n"
                "import sqlalchemy\n"
                "from fastapi import FastAPI\n"
                "from tenacity import retry\n"
                "TOKEN = os.getenv('TOKEN')\n"
            ),
            "compose.yaml": "services: {}\n",
            "deploy.yaml": "apiVersion: apps/v1\nkind: Deployment\n",
            "template.yaml": "AWSTemplateFormatVersion: '2010-09-09'\n",
            "test/test_app.py": "def test_app():\n    assert True\n",
            "ui/app.tsx": 'import React from "react";\n',
        },
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    required_standard_set = set(payload["project_list"][0]["required_standard_list"])
    assert {
        "aws-cloudformation-developer",
        "docker-compose-developer",
        "http-api-client-developer",
        "kubernetes-developer",
        "project-documentation-developer",
        "project-foundation",
        "project-instruction-developer",
        "pytest-developer",
        "python-cli-developer",
        "python-developer",
        "python-logging-developer",
        "python-retry-developer",
        "react-ui-developer",
        "rest-api-server-developer",
        "runtime-config-developer",
        "sqlalchemy-developer",
        "submodule-developer",
        "typescript-developer",
    } <= required_standard_set


def test_check_reports_missing_instruction_metadata_without_writing(tmp_path: Path) -> None:
    """Default check mode reports missing metadata and preserves the worktree.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    project_path = _project_create(workspace_root, "empty", {"README.md": "# Empty\n"})

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    assert not (project_path / "AGENTS.md").exists()
    report = json.loads(result.stdout)["project_list"][0]
    assert report["missing_metadata_list"] == ["AGENTS.md", "Required Standards"]


def test_check_ignores_instruction_examples_and_string_fixtures(tmp_path: Path) -> None:
    """Classification does not turn documented technology names into runtime capabilities.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _project_create(
        workspace_root,
        "provider",
        {
            "AGENTS.md": (
                "# Repository Guidelines\n\n"
                "## Required Standards\n\n"
                "- `project-standards:project-foundation` applies repository-wide.\n"
                "- `project-standards:project-instruction-developer` applies to instructions.\n"
                "- `project-standards:pytest-developer` applies to tests.\n"
                "- `project-standards:python-developer` applies to Python code.\n"
            ),
            "plugins/example/skills/reference.md": (
                "Examples mention SQLAlchemy, FastAPI, requests, retry_runtime, AWS::CloudFormation, React, and Legacy.\n"
            ),
            "test/test_fixture.py": (
                'SOURCE = """import sqlalchemy\\nfrom fastapi import FastAPI\\nimport requests\\nfrom tenacity import retry\\n"""\n'
                "\n"
                "def test_fixture() -> None:\n"
                "    assert SOURCE\n"
            ),
        },
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 0
    required_standard_list = json.loads(result.stdout)["project_list"][0]["required_standard_list"]
    assert required_standard_list == [
        "project-foundation",
        "project-instruction-developer",
        "pytest-developer",
        "python-developer",
    ]


def test_check_reports_unavailable_declared_provider_skill(tmp_path: Path) -> None:
    """A provider-qualified selection fails closed when its skill is unavailable.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _project_create(
        workspace_root,
        "invalid-provider",
        {
            "AGENTS.md": (
                "# Repository Guidelines\n\n"
                "## Required Standards\n\n"
                "- `project-standards:project-foundation` applies repository-wide.\n"
                "- `project-standards:project-instruction-developer` applies to instructions.\n"
                "- `project-standards:missing-standard` applies to a nonexistent boundary.\n"
            )
        },
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    report = json.loads(result.stdout)["project_list"][0]
    assert report["missing_standard_list"] == []
    assert report["unavailable_standard_list"] == ["missing-standard"]


def test_write_preserves_project_overlay_and_rechecks_result(tmp_path: Path) -> None:
    """Write mode adds selections without replacing project-local prose.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    project_path = _project_create(
        workspace_root,
        "consumer",
        {"AGENTS.md": ("# Consumer\n\n" "## Project Contract\n\n" "This exact local overlay must remain unchanged.\n")},
    )

    result = _tool_run(workspace_root, "--write")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["is_valid"] is True
    text = (project_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "This exact local overlay must remain unchanged." in text
    assert text.count("## Project Contract") == 1
    assert "`project-standards:project-foundation`" in text
    assert "`project-standards:project-instruction-developer`" in text


def test_write_refuses_multiple_worktrees_of_one_repository(tmp_path: Path) -> None:
    """Write mode refuses ambiguous edits when two discovered paths share Git state.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    primary_path = _project_create(workspace_root, "primary", {"README.md": "# Primary\n"})
    subprocess.run(["git", "add", "."], check=True, cwd=primary_path)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"],
        check=True,
        cwd=primary_path,
    )
    subprocess.run(["git", "worktree", "add", "-q", str(workspace_root / "secondary")], check=True, cwd=primary_path)

    result = _tool_run(workspace_root, "--write")

    assert result.returncode != 0
    assert "Refusing to edit multiple worktrees" in result.stderr
    assert not (primary_path / "AGENTS.md").exists()
    assert not (workspace_root / "secondary" / "AGENTS.md").exists()


def test_tool_source_has_no_workspace_specific_path() -> None:
    """The generic implementation must not encode the current user's workspace."""

    source = TOOL_PATH.read_text(encoding="utf-8")

    assert "/home/andrey/Projects" not in source
