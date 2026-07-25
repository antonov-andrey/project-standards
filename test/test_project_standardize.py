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


def test_check_classifies_kubernetes_integration_variants(tmp_path: Path) -> None:
    """Kubernetes classification accepts resources, Helm, Kustomize, and executable clients.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _project_create(
        workspace_root,
        "client",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "app.py": "from kubernetes import client\n",
        },
    )
    _project_create(
        workspace_root,
        "client-asyncio",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "app.py": "from kubernetes_asyncio import client\n",
        },
    )
    _project_create(
        workspace_root,
        "client-go",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "main.go": 'package main\n\nimport "k8s.io/client-go/kubernetes"\n',
        },
    )
    _project_create(
        workspace_root,
        "client-java",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "Main.java": "import io.kubernetes.client.openapi.ApiClient;\n",
        },
    )
    _project_create(
        workspace_root,
        "client-node",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "app.ts": 'import * as k8s from "@kubernetes/client-node";\n',
        },
    )
    _project_create(
        workspace_root,
        "client-rust",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "main.rs": "use kube::Client;\n",
        },
    )
    _project_create(
        workspace_root,
        "helm",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "deploy/chart/Chart.yaml": "apiVersion: v2\nname: application\n",
        },
    )
    _project_create(
        workspace_root,
        "kustomize",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "deploy/kustomization.yaml": "resources:\n  - deployment.yaml\n",
        },
    )
    _project_create(
        workspace_root,
        "resource",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "deploy/namespace.yaml": "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: application\n",
        },
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    report_by_name_map = {Path(report["path"]).name: report for report in json.loads(result.stdout)["project_list"]}
    assert set(report_by_name_map) == {
        "client",
        "client-asyncio",
        "client-go",
        "client-java",
        "client-node",
        "client-rust",
        "helm",
        "kustomize",
        "resource",
    }
    for report in report_by_name_map.values():
        assert "kubernetes-developer" in report["required_standard_list"]


def test_check_classifies_zitadel_integration_and_reports_missing_selection(tmp_path: Path) -> None:
    """A real ZITADEL deployment requires the available identity standard.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _project_create(
        workspace_root,
        "identity",
        {
            "AGENTS.md": (
                "# Repository Guidelines\n\n"
                "## Table Of Contents\n\n"
                "- [Required Standards](#required-standards)\n\n"
                "## Required Standards\n\n"
                "- `project-standards:project-foundation` applies repository-wide.\n"
                "- `project-standards:project-instruction-developer` applies to instructions.\n"
            ),
            "deploy/helm/zitadel/values.yaml": "image:\n  repository: ghcr.io/zitadel/zitadel\n",
        },
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    report = json.loads(result.stdout)["project_list"][0]
    assert "zitadel-developer" in report["required_standard_list"]
    assert report["missing_standard_list"] == ["zitadel-developer"]
    assert report["unavailable_standard_list"] == []


def test_check_classifies_zitadel_client_and_bound_oidc_configuration(tmp_path: Path) -> None:
    """Dedicated ZITADEL client and bound OIDC code both select the identity standard.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _project_create(
        workspace_root,
        "client",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "src/zitadel_client.py": "import httpx\n\nURL = '/v2/users'\n",
        },
    )
    _project_create(
        workspace_root,
        "oidc",
        {
            "AGENTS.md": "# Repository Guidelines\n",
            "src/auth/zitadel_auth/auth_config.ts": (
                'import { AuthProvider } from "react-oidc-context";\n'
                'export const authority = "https://identity.example.test";\n'
            ),
        },
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    for report in json.loads(result.stdout)["project_list"]:
        assert "zitadel-developer" in report["required_standard_list"]


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
    assert report["missing_metadata_list"] == ["AGENTS.md", "Table Of Contents", "Required Standards"]


def test_check_reports_table_of_contents_that_does_not_match_heading_order(tmp_path: Path) -> None:
    """Instruction validation rejects an incomplete or reordered table of contents.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _project_create(
        workspace_root,
        "invalid-instructions",
        {
            "AGENTS.md": (
                "# Repository Guidelines\n\n"
                "## Table Of Contents\n\n"
                "- [Project Contract](#project-contract)\n"
                "- [Required Standards](#required-standards)\n\n"
                "## Required Standards\n\n"
                "- `project-standards:project-foundation` applies repository-wide.\n"
                "- `project-standards:project-instruction-developer` applies to instructions.\n\n"
                "## Project Contract\n\n"
                "Project-specific behavior remains local.\n"
            )
        },
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 1
    report = json.loads(result.stdout)["project_list"][0]
    assert report["missing_metadata_list"] == ["Table Of Contents"]


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
                "## Table Of Contents\n\n"
                "- [Required Standards](#required-standards)\n\n"
                "## Required Standards\n\n"
                "- `project-standards:project-foundation` applies repository-wide.\n"
                "- `project-standards:project-instruction-developer` applies to instructions.\n"
                "- `project-standards:pytest-developer` applies to tests.\n"
                "- `project-standards:python-developer` applies to Python code.\n"
            ),
            "plugins/example/skills/reference.md": (
                "Examples mention SQLAlchemy, FastAPI, requests, retry_runtime, AWS::CloudFormation, React, Kubernetes, ZITADEL, and Legacy.\n"
            ),
            "test/fixtures/deploy/zitadel.yaml": "apiVersion: v1\nkind: Namespace\nname: zitadel\n",
            "test/test_fixture.py": (
                'SOURCE = """import sqlalchemy\\nfrom fastapi import FastAPI\\nimport requests\\nfrom kubernetes import client\\nfrom tenacity import retry\\nZITADEL\\n"""\n'
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


def test_check_ignores_zitadel_identity_and_proxy_path_without_integration(tmp_path: Path) -> None:
    """Foreign identity fields and VPN proxy values do not prove ZITADEL integration.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _project_create(
        workspace_root,
        "browser-runtime",
        {
            "AGENTS.md": (
                "# Repository Guidelines\n\n"
                "## Table Of Contents\n\n"
                "- [Required Standards](#required-standards)\n\n"
                "## Required Standards\n\n"
                "- `project-standards:project-foundation` applies repository-wide.\n"
                "- `project-standards:project-instruction-developer` applies to instructions.\n"
                "- `project-standards:python-developer` applies to Python code.\n"
            ),
            "runtime.py": (
                "def proxy_url_get(zitadel_user_id: str, vpn_config_name: str) -> str:\n"
                '    return f"{zitadel_user_id}/{vpn_config_name}"\n'
            ),
        },
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 0
    required_standard_list = json.loads(result.stdout)["project_list"][0]["required_standard_list"]
    assert "zitadel-developer" not in required_standard_list


def test_check_ignores_generic_oidc_and_zitadel_path_without_integration(tmp_path: Path) -> None:
    """Generic OIDC code and one named path do not prove a ZITADEL boundary.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _project_create(
        workspace_root,
        "generic-oidc",
        {
            "AGENTS.md": (
                "# Repository Guidelines\n\n"
                "## Table Of Contents\n\n"
                "- [Required Standards](#required-standards)\n\n"
                "## Required Standards\n\n"
                "- `project-standards:project-foundation` applies repository-wide.\n"
                "- `project-standards:project-instruction-developer` applies to instructions.\n"
                "- `project-standards:typescript-developer` applies to TypeScript code.\n"
            ),
            "src/auth_config.ts": (
                'import { UserManager } from "oidc-client-ts";\n'
                'export const authority = "https://identity.example.test";\n'
                'export const detectorSignature = "urn:zitadel:";\n'
            ),
        },
    )
    _project_create(
        workspace_root,
        "zitadel-path-only",
        {
            "AGENTS.md": (
                "# Repository Guidelines\n\n"
                "## Table Of Contents\n\n"
                "- [Required Standards](#required-standards)\n\n"
                "## Required Standards\n\n"
                "- `project-standards:project-foundation` applies repository-wide.\n"
                "- `project-standards:project-instruction-developer` applies to instructions.\n"
            ),
            "deploy/zitadel/values.yaml": "replicaCount: 1\n",
        },
    )

    result = _tool_run(workspace_root)

    assert result.returncode == 0
    for report in json.loads(result.stdout)["project_list"]:
        assert "zitadel-developer" not in report["required_standard_list"]


def test_check_skips_gitlink_directories_during_integration_scan(tmp_path: Path) -> None:
    """Gitlink paths are metadata entries rather than readable source files.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    project_path = _project_create(
        workspace_root,
        "host",
        {
            "AGENTS.md": (
                "# Repository Guidelines\n\n"
                "## Table Of Contents\n\n"
                "- [Required Standards](#required-standards)\n\n"
                "## Required Standards\n\n"
                "- `project-standards:project-foundation` applies repository-wide.\n"
                "- `project-standards:project-instruction-developer` applies to instructions.\n"
            ),
        },
    )
    gitlink_path = project_path / "base_api_schema"
    gitlink_path.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], check=True, cwd=gitlink_path)
    (gitlink_path / "README.md").write_text("# Provider\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], check=True, cwd=gitlink_path)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"],
        check=True,
        cwd=gitlink_path,
    )
    subprocess.run(["git", "add", "base_api_schema"], capture_output=True, check=True, cwd=project_path, text=True)

    result = _tool_run(workspace_root)

    assert result.returncode == 0
    report = json.loads(result.stdout)["project_list"][0]
    assert report["required_standard_list"] == ["project-foundation", "project-instruction-developer"]


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
                "## Table Of Contents\n\n"
                "- [Required Standards](#required-standards)\n\n"
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


def test_check_skips_tracked_files_deleted_from_worktree(tmp_path: Path) -> None:
    """Classification must ignore paths removed during an active migration.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    project_path = _project_create(
        workspace_root,
        "migration",
        {
            "AGENTS.md": (
                "# Repository Guidelines\n\n"
                "## Table Of Contents\n\n"
                "- [Required Standards](#required-standards)\n\n"
                "## Required Standards\n\n"
                "- `project-standards:project-foundation` applies repository-wide.\n"
                "- `project-standards:project-instruction-developer` applies to instructions.\n"
            ),
            "retired.py": "import sqlalchemy\n",
        },
    )
    subprocess.run(["git", "add", "."], check=True, cwd=project_path)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"],
        check=True,
        cwd=project_path,
    )
    (project_path / "retired.py").unlink()

    result = _tool_run(workspace_root)

    assert result.returncode == 0
    report = json.loads(result.stdout)["project_list"][0]
    assert report["required_standard_list"] == ["project-foundation", "project-instruction-developer"]


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
        {
            "AGENTS.md": (
                "# Consumer\n\n"
                "## Table Of Contents\n\n"
                "- [Project Contract](#project-contract)\n"
                "- [Required Standards](#required-standards)\n\n"
                "## Project Contract\n\n"
                "This exact local overlay must remain unchanged.\n"
            )
        },
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


def test_write_creates_complete_instruction_metadata_for_new_project(tmp_path: Path) -> None:
    """Write mode creates a project instruction file that passes its own follow-up check.

    Args:
        tmp_path: Isolated workspace parent.
    """

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _project_create(workspace_root, "new-project", {"README.md": "# New project\n"})

    write_result = _tool_run(workspace_root, "--write")
    check_result = _tool_run(workspace_root)

    assert write_result.returncode == 0
    assert json.loads(write_result.stdout)["is_valid"] is True
    assert check_result.returncode == 0
    assert json.loads(check_result.stdout)["is_valid"] is True


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
