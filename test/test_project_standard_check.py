"""Behavior tests for the project-standard checker runner and process protocol."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from project_standards import project_standard_check

CHECKER_ERROR_SOURCE = """\
import sys

sys.stdout.write("not-json\\n")
raise SystemExit(1)
"""
CHECKER_EXIT_ONE_EMPTY_SOURCE = """\
raise SystemExit(1)
"""
CHECKER_EXIT_THREE_SOURCE = """\
import sys

sys.stderr.write("unsupported failure\\n")
raise SystemExit(3)
"""
CHECKER_EXIT_TWO_SOURCE = """\
import sys

sys.stderr.write("checker failure\\n")
raise SystemExit(2)
"""
CHECKER_EXIT_TWO_WITH_STDOUT_SOURCE = """\
import sys

sys.stdout.write("{}\\n")
sys.stderr.write("checker failure\\n")
raise SystemExit(2)
"""
CHECKER_EXIT_ZERO_WITH_STDOUT_SOURCE = """\
import sys

sys.stdout.write("{}\\n")
raise SystemExit(0)
"""
CHECKER_FINDING_SOURCE = """\
import json
import sys

request = json.loads(sys.stdin.read())
assert set(request) == {"path_list", "project_root", "protocol_version", "scope"}
print(json.dumps({"path": request["path_list"][0], "line": 1, "message": "forbidden sample"}))
raise SystemExit(1)
"""
CHECKER_FINDING_UNSORTED_SOURCE = """\
import json

print(json.dumps({"path": "z.py", "message": "last"}))
print(json.dumps({"path": "a.py", "line": 8, "message": "first"}))
raise SystemExit(1)
"""
CHECKER_MUTATION_SOURCE = """\
import json
from pathlib import Path
import sys

request = json.loads(sys.stdin.read())
(Path(request["project_root"]) / "checker-created.txt").write_text("mutation\\n", encoding="utf-8")
raise SystemExit(0)
"""
CHECKER_SUCCESS_SOURCE = """\
import json
import sys

request = json.loads(sys.stdin.read())
assert request["protocol_version"] == 1
assert request["scope"] in {"all", "changed"}
assert request["path_list"] == sorted(set(request["path_list"]))
raise SystemExit(0)
"""
CHECKER_SUBMODULE_HOST_SOURCE = """\
import json
import sys

request = json.loads(sys.stdin.read())
assert request["path_list"]
assert all(not path.startswith("provider/") for path in request["path_list"])
raise SystemExit(0)
"""


class DistributionStub:
    """Locate package assets below one isolated distribution root."""

    def __init__(self, root: Path) -> None:
        """Store the isolated distribution root.

        Args:
            root: Temporary distribution root.
        """

        self.root = root

    def locate_file(self, relative_path: str) -> Path:
        """Resolve one installed-distribution-relative asset.

        Args:
            relative_path: Distribution-relative path requested by the runner.

        Returns:
            Resolved fixture path.
        """

        return self.root / relative_path


def _checker_manifest_write(
    asset_root: Path,
    check_source_by_id_map: dict[str, str],
    *,
    scope_strategy: str = "path-local",
) -> None:
    """Create one provider capability manifest and its checker scripts.

    Args:
        asset_root: Temporary capability asset root.
        check_source_by_id_map: Script source keyed by checker id.
        scope_strategy: Scope strategy written for every checker.
    """

    script_root = asset_root / "scripts"
    script_root.mkdir(parents=True)
    check_block_list: list[str] = []
    for checker_id, source in sorted(check_source_by_id_map.items()):
        script_name = f"{checker_id.replace('.', '_')}.py"
        (script_root / script_name).write_text(source, encoding="utf-8")
        check_block_list.append(
            "\n".join(
                [
                    "[[check_list]]",
                    f'id = "{checker_id}"',
                    f'script_path = "scripts/{script_name}"',
                    f'scope_strategy = "{scope_strategy}"',
                    'path_include_glob_list = ["**/*.py"]',
                ]
            )
        )
    (asset_root / "checker.toml").write_text(
        "\n\n".join(
            [
                "schema_version = 1",
                'owner = "project-standards:python-developer"',
                *check_block_list,
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _project_create(tmp_path: Path) -> Path:
    """Create one isolated governed Git project.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Initialized project root.
    """

    project_root = tmp_path / "project"
    project_root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project_root, check=True)
    (project_root / "AGENTS.md").write_text(
        (
            "# Repository Guidelines\n\n"
            "## Required Standards\n\n"
            "- `project-standards:python-developer` applies to Python code.\n"
        ),
        encoding="utf-8",
    )
    (project_root / "app.py").write_text('"""Application fixture."""\n', encoding="utf-8")
    return project_root


def _runner_run(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    project_root: Path,
    distribution_root: Path,
    *,
    scope: str,
) -> tuple[int, dict[str, object]]:
    """Run the real aggregate main function against isolated assets.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        project_root: Isolated target Git worktree.
        distribution_root: Isolated installed-distribution root.
        scope: Public runner scope.

    Returns:
        Exit code and JSON result payload.
    """

    monkeypatch.setattr(
        project_standard_check.metadata,
        "distribution",
        lambda distribution_name: DistributionStub(distribution_root),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "project-standard-check",
            "--project-root",
            str(project_root),
            "--scope",
            scope,
        ],
    )
    exit_code = project_standard_check.main()
    output = capsys.readouterr()
    assert output.err == ""
    return exit_code, json.loads(output.out)


def test_runner_returns_zero_for_one_successful_selected_checker(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A selected conforming checker returns one deterministic success document.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    distribution_root = tmp_path / "distribution"
    _checker_manifest_write(
        distribution_root / "project_standards" / "checker_assets" / "python-developer",
        {"python.success": CHECKER_SUCCESS_SOURCE},
    )

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        distribution_root,
        scope="all",
    )

    assert exit_code == 0
    assert payload == {
        "mechanical_checker_count": 1,
        "mechanical_error_list": [],
        "mechanical_finding_list": [],
        "mechanical_status": "clean",
        "scope": "all",
        "semantic_audit_required": True,
    }


def test_runner_enriches_and_sorts_one_checker_finding(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Untrusted checker output receives its manifest-owned identity.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    distribution_root = tmp_path / "distribution"
    _checker_manifest_write(
        distribution_root / "project_standards" / "checker_assets" / "python-developer",
        {"python.finding": CHECKER_FINDING_SOURCE},
    )

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        distribution_root,
        scope="all",
    )

    assert exit_code == 1
    assert payload["mechanical_status"] == "finding"
    assert payload["mechanical_finding_list"] == [
        {
            "id": "python.finding",
            "line": 1,
            "message": "forbidden sample",
            "owner": "project-standards:python-developer",
            "path": "app.py",
        }
    ]


def test_runner_collects_finding_after_another_checker_protocol_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """One broken checker does not hide valid results from another checker.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    distribution_root = tmp_path / "distribution"
    _checker_manifest_write(
        distribution_root / "project_standards" / "checker_assets" / "python-developer",
        {
            "python.error": CHECKER_ERROR_SOURCE,
            "python.finding": CHECKER_FINDING_SOURCE,
        },
    )

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        distribution_root,
        scope="all",
    )

    assert exit_code == 2
    assert payload["mechanical_checker_count"] == 2
    assert payload["mechanical_error_list"][0]["id"] == "python.error"
    assert payload["mechanical_finding_list"][0]["id"] == "python.finding"
    assert payload["mechanical_status"] == "error"


def test_runner_detects_checker_worktree_mutation(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A checker that mutates Git-visible target state makes the run fail.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    distribution_root = tmp_path / "distribution"
    _checker_manifest_write(
        distribution_root / "project_standards" / "checker_assets" / "python-developer",
        {"python.mutation": CHECKER_MUTATION_SOURCE},
    )

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        distribution_root,
        scope="all",
    )

    assert exit_code == 2
    assert payload["mechanical_error_list"] == [
        {
            "id": "<mutation>",
            "message": "Checker execution changed Git-visible target worktree state",
            "owner": "project-standards",
        }
    ]


def test_changed_scope_skips_selected_checker_without_applicable_changes(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Clean changed scope returns one informational success with no invocation.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    subprocess.run(["git", "add", "."], cwd=project_root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "user.name=Test",
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        cwd=project_root,
        check=True,
    )
    distribution_root = tmp_path / "distribution"
    _checker_manifest_write(
        distribution_root / "project_standards" / "checker_assets" / "python-developer",
        {"python.success": CHECKER_SUCCESS_SOURCE},
    )

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        distribution_root,
        scope="changed",
    )

    assert exit_code == 0
    assert payload["mechanical_checker_count"] == 0
    assert payload["mechanical_status"] == "clean"


def test_runner_rejects_non_root_and_missing_project_paths(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Only one existing exact Git worktree root is accepted.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    nested_path = project_root / "nested"
    nested_path.mkdir()
    for invalid_path in (nested_path, tmp_path / "missing"):
        exit_code, payload = _runner_run(
            capsys,
            monkeypatch,
            invalid_path,
            tmp_path / "distribution",
            scope="all",
        )
        assert exit_code == 2
        assert payload["mechanical_checker_count"] == 0
        assert payload["mechanical_error_list"][0]["id"] == "<project-root>"
        assert payload["mechanical_status"] == "error"


def test_runner_reports_scope_resolution_failure_as_deterministic_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A Git scope failure returns the structured runner error contract.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)

    def project_relpath_list_get(project_root: Path, scope: str) -> list[str]:
        """Raise the synthetic scope failure.

        Args:
            project_root: Exact project root.
            scope: Requested path scope.

        Returns:
            Repository paths when resolution succeeds.

        Raises:
            ValueError: Always for this failure fixture.
        """

        raise ValueError(f"unable to resolve {scope} paths below {project_root}")

    monkeypatch.setattr(project_standard_check, "project_relpath_list_get", project_relpath_list_get)

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        tmp_path / "distribution",
        scope="all",
    )

    assert exit_code == 2
    assert payload["mechanical_checker_count"] == 0
    assert payload["mechanical_error_list"] == [
        {
            "id": "<scope>",
            "message": f"unable to resolve all paths below {project_root}",
            "owner": "project-standards",
        }
    ]
    assert payload["mechanical_status"] == "error"


def test_runner_reports_invalid_manifest_and_missing_checker_script(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manifest load failures become deterministic runner errors.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    distribution_root = tmp_path / "distribution"
    asset_root = distribution_root / "project_standards" / "checker_assets" / "python-developer"
    _checker_manifest_write(asset_root, {"python.success": CHECKER_SUCCESS_SOURCE})
    manifest_path = asset_root / "checker.toml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            'owner = "project-standards:python-developer"',
            'owner = "project-standards:other"',
        ),
        encoding="utf-8",
    )

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        distribution_root,
        scope="all",
    )

    assert exit_code == 2
    assert payload["mechanical_checker_count"] == 0
    assert payload["mechanical_error_list"][0]["id"] == "<manifest>"
    assert "does not match" in payload["mechanical_error_list"][0]["message"]

    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            'owner = "project-standards:other"',
            'owner = "project-standards:python-developer"',
        ),
        encoding="utf-8",
    )
    (asset_root / "scripts" / "python_success.py").unlink()
    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        distribution_root,
        scope="all",
    )
    assert exit_code == 2
    assert payload["mechanical_checker_count"] == 0
    assert "owner-local file" in payload["mechanical_error_list"][0]["message"]


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (CHECKER_EXIT_ZERO_WITH_STDOUT_SOURCE, "exit 0 requires empty stdout"),
        (CHECKER_EXIT_ONE_EMPTY_SOURCE, "exit 1 requires at least one finding"),
        (CHECKER_EXIT_TWO_SOURCE, "checker failure"),
        (CHECKER_EXIT_TWO_WITH_STDOUT_SOURCE, "exit 2 requires empty stdout"),
        (CHECKER_EXIT_THREE_SOURCE, "unsupported exit code 3"),
    ],
)
def test_runner_maps_every_checker_exit_contract_to_execution_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source: str,
    message: str,
) -> None:
    """Checker process exit and stream inconsistencies produce exit two.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
        source: Checker process fixture source.
        message: Expected aggregate diagnostic fragment.
    """

    project_root = _project_create(tmp_path)
    distribution_root = tmp_path / "distribution"
    _checker_manifest_write(
        distribution_root / "project_standards" / "checker_assets" / "python-developer",
        {"python.process": source},
    )

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        distribution_root,
        scope="all",
    )

    assert exit_code == 2
    assert payload["mechanical_checker_count"] == 1
    assert message in payload["mechanical_error_list"][0]["message"]
    assert payload["mechanical_status"] == "error"


def test_runner_ignores_unselected_capability_and_sorts_checkers_and_findings(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Selection is canonical and aggregate order is independent of manifest order.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    distribution_root = tmp_path / "distribution"
    asset_root = distribution_root / "project_standards" / "checker_assets"
    _checker_manifest_write(
        asset_root / "python-developer",
        {
            "python.zeta": CHECKER_FINDING_UNSORTED_SOURCE,
            "python.alpha": CHECKER_FINDING_UNSORTED_SOURCE,
        },
    )
    unselected_root = asset_root / "project-foundation"
    unselected_root.mkdir(parents=True)
    (unselected_root / "checker.toml").write_text("invalid = true\n", encoding="utf-8")

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        distribution_root,
        scope="all",
    )

    assert exit_code == 1
    assert payload["mechanical_checker_count"] == 2
    assert [
        (finding["id"], finding["path"], finding.get("line")) for finding in payload["mechanical_finding_list"]
    ] == [
        ("python.alpha", "a.py", 8),
        ("python.alpha", "z.py", None),
        ("python.zeta", "a.py", 8),
        ("python.zeta", "z.py", None),
    ]
    assert payload["mechanical_status"] == "finding"


def test_runner_executes_checker_with_current_python_without_shell(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The trusted process boundary uses the current interpreter directly.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    distribution_root = tmp_path / "distribution"
    asset_root = distribution_root / "project_standards" / "checker_assets" / "python-developer"
    _checker_manifest_write(asset_root, {"python.success": CHECKER_SUCCESS_SOURCE})
    call_list: list[tuple[list[str], dict[str, object]]] = []

    def subprocess_run(argument_list: list[str], **keyword_by_name_map: object) -> subprocess.CompletedProcess[str]:
        """Record and satisfy the one checker subprocess call.

        Args:
            argument_list: Direct process argument vector.
            keyword_by_name_map: Subprocess keyword arguments.

        Returns:
            Successful checker process result.
        """

        call_list.append((argument_list, keyword_by_name_map))
        return subprocess.CompletedProcess(argument_list, 0, "", "")

    monkeypatch.setattr(project_standard_check, "subprocess", SimpleNamespace(run=subprocess_run))

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        distribution_root,
        scope="all",
    )

    assert exit_code == 0
    assert payload["mechanical_checker_count"] == 1
    assert len(call_list) == 1
    argument_list, keyword_by_name_map = call_list[0]
    assert argument_list == [sys.executable, str((asset_root / "scripts" / "python_success.py").resolve())]
    assert "shell" not in keyword_by_name_map
    assert keyword_by_name_map["cwd"] == project_root
    request = json.loads(str(keyword_by_name_map["input"]))
    assert request["project_root"] == str(project_root)
    assert request["path_list"] == ["app.py"]


def test_capability_checker_scope_excludes_direct_submodule_code() -> None:
    """A consumer capability checker never classifies code owned by a Submodule."""

    assert project_standard_check._checker_visible_path_list_get(
        path_list=["app.py", "provider", "provider/module.py"],
        submodule_name_by_path_map={"provider": "provider"},
    ) == ["app.py"]


def test_runner_discovers_direct_submodule_host_checker(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """One exact checked-out direct submodule contributes its host checker.

    Args:
        capsys: Pytest output capture fixture.
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Pytest temporary directory.
    """

    project_root = _project_create(tmp_path)
    provider_root = project_root / "provider"
    provider_root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=provider_root, check=True)
    script_root = provider_root / "scripts"
    script_root.mkdir()
    (script_root / "host.py").write_text(CHECKER_SUBMODULE_HOST_SOURCE, encoding="utf-8")
    (provider_root / "project-standard-check.toml").write_text(
        (
            "schema_version = 1\n"
            'owner = "submodule:provider"\n'
            "\n"
            "[[check_list]]\n"
            'id = "provider.host"\n'
            'script_path = "scripts/host.py"\n'
            'scope_strategy = "full-on-change"\n'
            'path_include_glob_list = ["**/*"]\n'
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=provider_root, check=True)
    (project_root / ".gitmodules").write_text(
        '[submodule "provider"]\n\tpath = provider\n\turl = https://example.invalid/provider.git\n',
        encoding="utf-8",
    )

    exit_code, payload = _runner_run(
        capsys,
        monkeypatch,
        project_root,
        tmp_path / "distribution",
        scope="all",
    )

    assert exit_code == 0
    assert payload["mechanical_checker_count"] == 1
    assert payload["mechanical_status"] == "clean"
