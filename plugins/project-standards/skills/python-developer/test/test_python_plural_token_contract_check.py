"""Behavior tests for provider-owned plural-token checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_plural_token_contract_check.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(
    project_root: Path, source: str, *, relative_path: str = "module.py"
) -> subprocess.CompletedProcess[str]:
    """Run the real plural-token checker against one synthetic repository.

    Args:
        project_root: Synthetic Git repository root.
        source: Python source under test.
        relative_path: Repository-relative source path.

    Returns:
        Completed checker process.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project_root, check=True)
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
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
                "path_list": [relative_path],
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_allows_singular_s_tokens_and_semantic_external_boundaries(tmp_path: Path) -> None:
    """Singular tokens and evidenced Helm or HTTP boundaries remain allowed.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "def kubernetes_status_get():\n"
            '    """Return Kubernetes status."""\n'
            "    return None\n\n"
            "def zitadel_values_digest_get():\n"
            '    """Return the Helm values digest."""\n'
            "    return None\n\n"
            "def too_many_requests_detect():\n"
            '    """Detect a Too Many Requests response."""\n'
            "    return None\n\n"
            "def class_allows_receiverless_bypass():\n"
            '    """Represent singular and verb tokens that end in s."""\n'
            "    return None\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_unowned_plural_tokens_and_keeps_exact_framework_names(tmp_path: Path) -> None:
    """Owner-controlled plurals fail while an exact argparse override passes.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic module."""\n\n'
            "def _split_lines(self, text: str):\n"
            '    """Implement the inherited formatter method."""\n'
            "    return text.splitlines()\n\n"
            "def runtime_values_digest_get():\n"
            '    """Return arbitrary runtime data."""\n'
            "    return None\n\n"
            "def products_get():\n"
            '    """Return products."""\n'
            "    return None\n"
        ),
        relative_path="plugins/config_argparse/parser.py",
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert [finding["line"] for finding in finding_list] == [7, 11]
    assert "values" in finding_list[0]["message"]
    assert "products" in finding_list[1]["message"]
    assert result.stderr == ""


def test_checker_allows_external_endpoint_names_only_at_the_provider_boundary(tmp_path: Path) -> None:
    """External endpoint names remain narrow to provider path or transport evidence.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        (
            '"""Synthetic provider module."""\n\n'
            "def product_info_attributes():\n"
            '    """Return external attributes."""\n'
            "    return None\n\n"
            "def product_discounts():\n"
            '    """Call one provider endpoint."""\n'
            "    return '/v1/product/discounts'\n"
        ),
        relative_path="plugins/ozon_seller_api/client.py",
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
