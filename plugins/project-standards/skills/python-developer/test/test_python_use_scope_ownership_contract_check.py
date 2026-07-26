"""Behavior tests for provider-owned Python use-scope ownership checking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

CHECKER_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check" / "python_use_scope_ownership_contract_check.py"
)
PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "lib"


def _checker_run(project_root: Path, relative_path_by_source_map: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the real ownership checker against synthetic modules.

    Args:
        project_root: Synthetic Git repository root.
        relative_path_by_source_map: Python source keyed by repository path.

    Returns:
        Completed checker process.
    """

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project_root, check=True)
    for relative_path, source in relative_path_by_source_map.items():
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
                "path_list": sorted(relative_path_by_source_map),
                "project_root": str(project_root.resolve()),
                "protocol_version": 1,
                "scope": "all",
            }
        ),
        text=True,
    )


def test_checker_accepts_shared_owner_for_multiple_script_slices(tmp_path: Path) -> None:
    """Cross-slice reuse belongs under one shared package.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/shared/value.py": '"""Shared value."""\n\ndef value_get() -> int:\n    return 1\n',
            "script/one/a.py": '"""First use."""\n\nfrom lib.shared.value import value_get\n\nVALUE = value_get()\n',
            "script/two/a.py": '"""Second use."""\n\nfrom lib.shared.value import value_get\n\nVALUE = value_get()\n',
        },
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_checker_reports_cross_slice_symbol_single_slice_package_and_forwarding_bridge(tmp_path: Path) -> None:
    """Primary placement and bridge violations retain useful diagnostics.

    Args:
        tmp_path: Pytest temporary directory.
    """

    result = _checker_run(
        tmp_path,
        {
            "lib/only/value.py": '"""Shared value."""\n\ndef value_get() -> int:\n    return 1\n',
            "script/one/bridge.py": '"""Bridge."""\n\nfrom lib.only.value import value_get\n',
            "script/one/use_a.py": (
                '"""First use."""\n\n' "from script.one.bridge import value_get\n\n" "VALUE = value_get()\n"
            ),
            "script/one/use_b.py": (
                '"""Second use."""\n\n' "from lib.only.value import value_get\n\n" "VALUE = value_get()\n"
            ),
            "script/two/use.py": (
                '"""Other slice use."""\n\n' "from script.one.bridge import value_get\n\n" "VALUE = value_get()\n"
            ),
        },
    )

    assert result.returncode == 1
    finding_list = [json.loads(line) for line in result.stdout.splitlines()]
    assert any(
        finding["path"] == "lib/only" and "used only inside script/one" in finding["message"]
        for finding in finding_list
    )
    assert any(
        finding["path"] == "script/one/bridge.py" and "forwarding import bridge value_get" in finding["message"]
        for finding in finding_list
    )
    assert result.stderr == ""
