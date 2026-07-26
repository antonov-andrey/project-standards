"""Behavior tests for Product API route-registration static checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "route_registration_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_list: list[str]) -> subprocess.CompletedProcess[str]:
    """Run the real checker process against one synthetic repository.

    Args:
        project_root: Exact synthetic repository root.
        relative_path_list: Current repository-relative path list.

    Returns:
        Completed checker process.
    """

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
                "path_list": sorted(relative_path_list),
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_accepts_canonical_router_infrastructure_and_custom_resource_hook(tmp_path: Path) -> None:
    """Canonical infrastructure and a real custom row hook produce no findings.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    router_path = project_root / "backend" / "api_router.py"
    router_path.parent.mkdir(parents=True)
    router_path.write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n",
        encoding="utf-8",
    )
    resource_path = project_root / "backend" / "api" / "item.py"
    resource_path.parent.mkdir()
    resource_path.write_text(
        (
            "class ItemApiResource(ProductApiResource):\n"
            "    def _row_create(self, payload):\n"
            "        return Item(name=payload.name)\n"
        ),
        encoding="utf-8",
    )

    result = _checker_run(
        project_root,
        ["backend/api/item.py", "backend/api_router.py"],
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_fastapi_bypass_duplicate_runtime_and_trivial_mapping(tmp_path: Path) -> None:
    """Every primary static Product API bypass branch reports its source line.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    resource_path = project_root / "backend" / "api" / "item.py"
    resource_path.parent.mkdir(parents=True)
    resource_path.write_text(
        (
            "from fastapi import APIRouter, FastAPI\n\n"
            "router = APIRouter()\n"
            "application = FastAPI()\n"
            "router.include_router(other)\n\n"
            "def _item_response_get(row):\n"
            "    return ItemResponse(**row.payload_get())\n\n"
            "class ItemApiResource(ProductApiResource):\n"
            "    def __init__(self):\n"
            "        super().__init__(response_get=_item_response_get)\n\n"
            "    @router.get('/item')\n"
            "    def item_get(self):\n"
            "        return None\n\n"
            "    def _item_create(self):\n"
            "        return None\n"
        ),
        encoding="utf-8",
    )

    result = _checker_run(project_root, ["backend/api/item.py"])

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    message_set = {finding["message"] for finding in finding_list}
    assert "direct APIRouter import is forbidden outside backend/api_router.py" in message_set
    assert "direct APIRouter() construction is forbidden outside backend/api_router.py" in message_set
    assert "direct FastAPI() construction is allowed only in backend/app.py" in message_set
    assert "direct include_router route registration is forbidden" in message_set
    assert "item_get uses one manual @get standard-resource route decorator" in message_set
    assert "_item_create duplicates standard ProductApiResource runtime" in message_set
    assert "_item_response_get duplicates generated standard response mapping" in message_set
    assert all(finding["path"] == "backend/api/item.py" for finding in finding_list)
    assert result.stderr == ""


def test_checker_rejects_manual_route_decorator_without_resource_class(tmp_path: Path) -> None:
    """A backend module cannot escape checking by omitting ProductApiResource.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    route_path = project_root / "backend" / "api" / "plain.py"
    route_path.parent.mkdir(parents=True)
    route_path.write_text(
        ("@router.post('/plain')\n" "def plain_create():\n" "    return None\n"),
        encoding="utf-8",
    )

    result = _checker_run(project_root, ["backend/api/plain.py"])

    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "line": 2,
        "message": "direct @post route decorator is forbidden",
        "path": "backend/api/plain.py",
    }
    assert result.stderr == ""
