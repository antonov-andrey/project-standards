"""Run selected provider and submodule conformance checks without mutations."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys
import tomllib

from pathspec import GitIgnoreSpec

from project_standards.git_repository import git_output_get, submodule_name_by_path_map_get
from project_standards.project_scope import project_relpath_list_get
from project_standards.project_standard_model import (
    ProjectStandardCheckerConfig,
    ProjectStandardExecutionError,
    ProjectStandardFinding,
    ProjectStandardRequest,
)
from project_standards.required_standard import required_standard_name_list_get

CHECKER_MANIFEST_FIELD_SET = {"check_list", "owner", "schema_version"}
CHECKER_REQUIRED_FIELD_SET = {"id", "path_include_glob_list", "scope_strategy", "script_path"}
CHECKER_SUPPORTED_FIELD_SET = CHECKER_REQUIRED_FIELD_SET | {
    "path_exclude_glob_list",
    "trigger_path_exclude_glob_list",
    "trigger_path_include_glob_list",
}
DISTRIBUTION_NAME = "project-standards"
PROTOCOL_VERSION = 1
SCOPE_STRATEGY_SET = {"full-on-change", "path-local"}


def _args_parse() -> argparse.Namespace:
    """Parse the exact public checker-runner command line.

    Returns:
        Parsed command-line namespace.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path, help="Exact target Git worktree root.")
    parser.add_argument("--scope", choices=("all", "changed"), required=True, help="Repository scope to check.")
    return parser.parse_args()


def _capability_checker_config_list_collect(
    project_root: Path,
    checker_config_list: list[ProjectStandardCheckerConfig],
    execution_error_list: list[ProjectStandardExecutionError],
) -> None:
    """Collect manifests for selected provider capabilities.

    Args:
        project_root: Exact consumer repository root.
        checker_config_list: Mutable normalized checker destination.
        execution_error_list: Mutable deterministic error destination.
    """

    try:
        distribution = metadata.distribution(DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError as error:
        execution_error_list.append(
            ProjectStandardExecutionError(
                id="<distribution>",
                message=f"Installed distribution {DISTRIBUTION_NAME!r} is unavailable: {error}",
                owner=DISTRIBUTION_NAME,
            )
        )
        return
    asset_root = Path(distribution.locate_file("project_standards/checker_assets")).resolve()
    for standard_name in required_standard_name_list_get(project_root / "AGENTS.md"):
        owner = f"project-standards:{standard_name}"
        owner_root = asset_root / standard_name
        manifest_path = owner_root / "checker.toml"
        if not manifest_path.is_file():
            continue
        try:
            checker_config_list.extend(
                _manifest_checker_config_list_get(
                    expected_owner=owner,
                    manifest_path=manifest_path,
                    owner_repository_path="",
                    owner_root=owner_root,
                )
            )
        except ValueError as error:
            execution_error_list.append(ProjectStandardExecutionError(id="<manifest>", message=str(error), owner=owner))


def _checker_config_list_dedupe(
    checker_config_list: list[ProjectStandardCheckerConfig],
    execution_error_list: list[ProjectStandardExecutionError],
) -> list[ProjectStandardCheckerConfig]:
    """Reject duplicate checker identities and return deterministic unique configs.

    Args:
        checker_config_list: Candidate normalized checker declarations.
        execution_error_list: Mutable deterministic error destination.

    Returns:
        Sorted checker configs whose identities are unique.
    """

    checker_config_by_identity_map: dict[str, ProjectStandardCheckerConfig] = {}
    duplicate_identity_set: set[str] = set()
    for checker_config in checker_config_list:
        identity = f"{checker_config['owner']}\0{checker_config['id']}"
        if identity in checker_config_by_identity_map:
            duplicate_identity_set.add(identity)
            continue
        checker_config_by_identity_map[identity] = checker_config
    for identity in sorted(duplicate_identity_set):
        owner, checker_id = identity.split("\0", maxsplit=1)
        execution_error_list.append(
            ProjectStandardExecutionError(
                id=checker_id,
                message=f"Duplicate checker identity: ({owner!r}, {checker_id!r})",
                owner=owner,
            )
        )
        checker_config_by_identity_map.pop(identity, None)
    return [checker_config_by_identity_map[identity] for identity in sorted(checker_config_by_identity_map)]


def _checker_finding_list_get(
    checker_config: ProjectStandardCheckerConfig,
    path_list: list[str],
    project_root: Path,
    scope: str,
) -> list[ProjectStandardFinding]:
    """Run one checker and return validated trusted findings.

    Args:
        checker_config: Normalized checker declaration.
        path_list: Deterministic paths selected for this checker.
        project_root: Exact consumer repository root.
        scope: Requested runner scope.

    Returns:
        Validated findings enriched with trusted checker identity.

    Raises:
        ValueError: Process output or exit semantics violate the protocol.
    """

    request = ProjectStandardRequest(
        path_list=path_list,
        project_root=str(project_root),
        protocol_version=PROTOCOL_VERSION,
        scope=scope,
    )
    result = subprocess.run(
        [sys.executable, str(checker_config["script_path"])],
        capture_output=True,
        check=False,
        cwd=project_root,
        input=json.dumps(request, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        text=True,
    )
    stdout = result.stdout
    stderr = result.stderr.strip()
    if result.returncode == 2:
        if stdout or not stderr:
            raise ValueError("Checker exit 2 requires empty stdout and one concrete stderr error")
        raise ValueError(stderr)
    if result.returncode not in {0, 1}:
        raise ValueError(f"Checker returned unsupported exit code {result.returncode}: {stderr}")
    if stderr:
        raise ValueError(f"Checker exit {result.returncode} wrote unexpected stderr: {stderr}")
    raw_line_list = stdout.splitlines()
    if result.returncode == 0 and raw_line_list:
        raise ValueError("Checker exit 0 requires empty stdout")
    if result.returncode == 1 and not raw_line_list:
        raise ValueError("Checker exit 1 requires at least one finding")
    finding_list: list[ProjectStandardFinding] = []
    for raw_line in raw_line_list:
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Checker emitted invalid JSON Lines output: {error}") from error
        _checker_finding_payload_validate(payload)
        finding = ProjectStandardFinding(
            id=checker_config["id"],
            message=payload["message"],
            owner=checker_config["owner"],
            path=payload["path"],
        )
        if "line" in payload:
            finding["line"] = payload["line"]
        finding_list.append(finding)
    return finding_list


def _checker_finding_payload_validate(payload: object) -> None:
    """Validate one untrusted checker finding payload.

    Args:
        payload: JSON-decoded checker output row.

    Raises:
        ValueError: The finding does not follow protocol version one.
    """

    if not isinstance(payload, dict) or set(payload) not in (
        {"message", "path"},
        {"line", "message", "path"},
    ):
        raise ValueError("Checker finding must contain only path, optional line, and message")
    relative_path = payload["path"]
    message = payload["message"]
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("Checker finding path must be one non-empty string")
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != relative_path:
        raise ValueError(f"Checker finding path is not canonical and relative: {relative_path!r}")
    if not isinstance(message, str) or not message:
        raise ValueError("Checker finding message must be one non-empty string")
    if "line" in payload and (not isinstance(payload["line"], int) or payload["line"] <= 0):
        raise ValueError("Checker finding line must be one positive integer")


def _checker_path_list_get(
    all_path_list: list[str],
    changed_path_list: list[str],
    checker_config: ProjectStandardCheckerConfig,
    scope: str,
    submodule_name_by_path_map: dict[str, str],
) -> list[str]:
    """Return paths selected by one checker declaration.

    Args:
        all_path_list: All current repository and direct-submodule paths.
        changed_path_list: Changed paths including deletions.
        checker_config: Normalized checker declaration.
        scope: Requested runner scope.
        submodule_name_by_path_map: Direct submodule names keyed by relative path.

    Returns:
        Deterministic current paths passed to the checker.
    """

    visible_all_path_list = _checker_visible_path_list_get(
        checker_config=checker_config,
        path_list=all_path_list,
        submodule_name_by_path_map=submodule_name_by_path_map,
    )
    if scope == "all" or checker_config["scope_strategy"] == "full-on-change":
        candidate_path_list = visible_all_path_list
    else:
        current_path_set = set(visible_all_path_list)
        candidate_path_list = [path for path in changed_path_list if path in current_path_set]
    return [
        relative_path
        for relative_path in candidate_path_list
        if _match_path_glob_list(
            exclude_glob_list=checker_config["path_exclude_glob_list"],
            include_glob_list=checker_config["path_include_glob_list"],
            relative_path=relative_path,
        )
    ]


def _checker_visible_path_list_get(
    checker_config: ProjectStandardCheckerConfig,
    path_list: list[str],
    submodule_name_by_path_map: dict[str, str],
) -> list[str]:
    """Return paths visible to a capability or host-conformance checker.

    Args:
        checker_config: Normalized checker declaration.
        path_list: Candidate consumer and direct-submodule paths.
        submodule_name_by_path_map: Direct submodule names keyed by relative path.

    Returns:
        Original paths for a capability or consumer-owned paths for a host checker.
    """

    if not checker_config["owner_repository_path"]:
        return path_list
    return [
        relative_path
        for relative_path in path_list
        if not any(
            relative_path == submodule_path or relative_path.startswith(f"{submodule_path}/")
            for submodule_path in submodule_name_by_path_map
        )
    ]


def _glob_list_get(
    raw_value: object,
    field_name: str,
    manifest_path: Path,
    require_nonempty: bool,
) -> list[str]:
    """Validate one manifest Git-wildmatch pattern list.

    Args:
        raw_value: Untrusted TOML field.
        field_name: Field name used in diagnostics.
        manifest_path: Owning manifest path.
        require_nonempty: Whether an empty list is forbidden.

    Returns:
        Validated pattern list.

    Raises:
        ValueError: The field is not one supported pattern list.
    """

    if not isinstance(raw_value, list) or any(not isinstance(item, str) for item in raw_value):
        raise ValueError(f"Checker manifest {manifest_path} field {field_name} must be one string list")
    if require_nonempty and not raw_value:
        raise ValueError(f"Checker manifest {manifest_path} field {field_name} must not be empty")
    if any(not item or item.startswith(("!", "/")) for item in raw_value):
        raise ValueError(
            f"Checker manifest {manifest_path} field {field_name} contains an empty, negated, or absolute pattern"
        )
    try:
        GitIgnoreSpec.from_lines(raw_value)
    except ValueError as error:
        raise ValueError(f"Checker manifest {manifest_path} field {field_name} is invalid: {error}") from error
    return list(raw_value)


def _manifest_checker_config_list_get(
    expected_owner: str,
    manifest_path: Path,
    owner_repository_path: str,
    owner_root: Path,
) -> list[ProjectStandardCheckerConfig]:
    """Load and normalize one exact checker manifest.

    Args:
        expected_owner: Trusted provider or submodule owner identity.
        manifest_path: Manifest file to parse.
        owner_repository_path: Consumer-relative submodule root or empty capability marker.
        owner_root: Filesystem root that owns checker scripts.

    Returns:
        Normalized checker declaration list.

    Raises:
        ValueError: The manifest violates version one.
    """

    try:
        payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"Unable to parse checker manifest {manifest_path}: {error}") from error
    if set(payload) != CHECKER_MANIFEST_FIELD_SET:
        raise ValueError(f"Checker manifest {manifest_path} has unsupported or missing root fields")
    if payload["schema_version"] != PROTOCOL_VERSION:
        raise ValueError(f"Checker manifest {manifest_path} has unsupported schema_version")
    if payload["owner"] != expected_owner:
        raise ValueError(
            f"Checker manifest {manifest_path} owner {payload['owner']!r} does not match {expected_owner!r}"
        )
    raw_check_list = payload["check_list"]
    if not isinstance(raw_check_list, list) or not raw_check_list:
        raise ValueError(f"Checker manifest {manifest_path} check_list must be one non-empty list")
    checker_config_list: list[ProjectStandardCheckerConfig] = []
    checker_id_set: set[str] = set()
    owner_root = owner_root.resolve()
    for raw_check in raw_check_list:
        if not isinstance(raw_check, dict):
            raise ValueError(f"Checker manifest {manifest_path} contains one non-table check")
        if not CHECKER_REQUIRED_FIELD_SET <= set(raw_check) or not set(raw_check) <= CHECKER_SUPPORTED_FIELD_SET:
            raise ValueError(f"Checker manifest {manifest_path} check has unsupported or missing fields")
        checker_id = _nonempty_string_get(raw_check["id"], field_name="id", manifest_path=manifest_path)
        if checker_id in checker_id_set:
            raise ValueError(f"Checker manifest {manifest_path} repeats id {checker_id!r}")
        checker_id_set.add(checker_id)
        script_relative_path = _relative_posix_path_get(
            raw_check["script_path"],
            field_name="script_path",
            manifest_path=manifest_path,
        )
        script_path = (owner_root / script_relative_path).resolve()
        if not script_path.is_relative_to(owner_root) or not script_path.is_file():
            raise ValueError(f"Checker manifest {manifest_path} script does not resolve to one owner-local file")
        scope_strategy = _nonempty_string_get(
            raw_check["scope_strategy"],
            field_name="scope_strategy",
            manifest_path=manifest_path,
        )
        if scope_strategy not in SCOPE_STRATEGY_SET:
            raise ValueError(f"Checker manifest {manifest_path} has unsupported scope_strategy {scope_strategy!r}")
        if owner_repository_path and scope_strategy != "full-on-change":
            raise ValueError(f"Submodule checker manifest {manifest_path} must use full-on-change")
        path_include_glob_list = _glob_list_get(
            raw_check["path_include_glob_list"],
            field_name="path_include_glob_list",
            manifest_path=manifest_path,
            require_nonempty=True,
        )
        path_exclude_glob_list = _glob_list_get(
            raw_check.get("path_exclude_glob_list", []),
            field_name="path_exclude_glob_list",
            manifest_path=manifest_path,
            require_nonempty=False,
        )
        checker_config_list.append(
            ProjectStandardCheckerConfig(
                id=checker_id,
                owner=expected_owner,
                owner_repository_path=owner_repository_path,
                owner_root=owner_root,
                path_exclude_glob_list=path_exclude_glob_list,
                path_include_glob_list=path_include_glob_list,
                scope_strategy=scope_strategy,
                script_path=script_path,
                trigger_path_exclude_glob_list=_glob_list_get(
                    raw_check.get("trigger_path_exclude_glob_list", path_exclude_glob_list),
                    field_name="trigger_path_exclude_glob_list",
                    manifest_path=manifest_path,
                    require_nonempty=False,
                ),
                trigger_path_include_glob_list=_glob_list_get(
                    raw_check.get("trigger_path_include_glob_list", path_include_glob_list),
                    field_name="trigger_path_include_glob_list",
                    manifest_path=manifest_path,
                    require_nonempty=True,
                ),
            )
        )
    return checker_config_list


def _match_path_glob_list(
    exclude_glob_list: list[str],
    include_glob_list: list[str],
    relative_path: str,
) -> bool:
    """Return whether one path matches includes and no excludes.

    Args:
        exclude_glob_list: Git-wildmatch exclusions.
        include_glob_list: Git-wildmatch inclusions.
        relative_path: Canonical repository-relative POSIX path.

    Returns:
        Whether the path is selected.
    """

    include_spec = GitIgnoreSpec.from_lines(include_glob_list)
    exclude_spec = GitIgnoreSpec.from_lines(exclude_glob_list)
    return include_spec.match_file(relative_path) and not exclude_spec.match_file(relative_path)


def _nonempty_string_get(raw_value: object, field_name: str, manifest_path: Path) -> str:
    """Validate one non-empty manifest string.

    Args:
        raw_value: Untrusted TOML field.
        field_name: Field name used in diagnostics.
        manifest_path: Owning manifest path.

    Returns:
        Validated string.

    Raises:
        ValueError: The field is not one non-empty string.
    """

    if not isinstance(raw_value, str) or not raw_value:
        raise ValueError(f"Checker manifest {manifest_path} field {field_name} must be one non-empty string")
    return raw_value


def _project_root_get(raw_project_root: Path) -> Path:
    """Validate and return one exact Git worktree root.

    Args:
        raw_project_root: User-supplied project root.

    Returns:
        Canonical absolute Git root.

    Raises:
        ValueError: The input is missing or is not the exact worktree root.
    """

    project_root = raw_project_root.resolve()
    if not project_root.is_dir():
        raise ValueError(f"Project root is not a directory: {project_root}")
    git_root = Path(git_output_get(project_root, ["rev-parse", "--show-toplevel"]).strip()).resolve()
    if git_root != project_root:
        raise ValueError(f"Project root must be the exact Git worktree root: {git_root}")
    return project_root


def _relative_posix_path_get(raw_value: object, field_name: str, manifest_path: Path) -> str:
    """Validate one manifest-relative POSIX path.

    Args:
        raw_value: Untrusted TOML field.
        field_name: Field name used in diagnostics.
        manifest_path: Owning manifest path.

    Returns:
        Canonical relative POSIX path.

    Raises:
        ValueError: The field is absolute, escaping, or non-canonical.
    """

    value = _nonempty_string_get(raw_value, field_name=field_name, manifest_path=manifest_path)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError(f"Checker manifest {manifest_path} field {field_name} must be one relative POSIX path")
    return value


def _result_print(
    checker_count: int,
    execution_error_list: list[ProjectStandardExecutionError],
    finding_list: list[ProjectStandardFinding],
    scope: str,
) -> None:
    """Print one deterministic runner result document.

    Args:
        checker_count: Number of invoked checker processes.
        execution_error_list: Collected runner and checker errors.
        finding_list: Collected conformance findings.
        scope: Requested runner scope.
    """

    execution_error_list.sort(key=lambda error: (error["owner"], error["id"], error["message"]))
    finding_list.sort(
        key=lambda finding: (
            finding["owner"],
            finding["id"],
            finding["path"],
            finding.get("line", 0),
            finding["message"],
        )
    )
    status = "error" if execution_error_list else "finding" if finding_list else "ok"
    print(
        json.dumps(
            {
                "checker_count": checker_count,
                "error_list": execution_error_list,
                "finding_list": finding_list,
                "scope": scope,
                "status": status,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _should_checker_run(
    changed_path_list: list[str],
    checker_config: ProjectStandardCheckerConfig,
    scope: str,
) -> bool:
    """Return whether one checker is active for the requested scope.

    Args:
        changed_path_list: Changed paths including deletions.
        checker_config: Normalized checker declaration.
        scope: Requested runner scope.

    Returns:
        Whether the checker process must run.
    """

    if scope == "all":
        return True
    owner_repository_path = checker_config["owner_repository_path"]
    if owner_repository_path and any(
        relative_path == owner_repository_path or relative_path.startswith(f"{owner_repository_path}/")
        for relative_path in changed_path_list
    ):
        return True
    return any(
        _match_path_glob_list(
            exclude_glob_list=checker_config["trigger_path_exclude_glob_list"],
            include_glob_list=checker_config["trigger_path_include_glob_list"],
            relative_path=relative_path,
        )
        for relative_path in changed_path_list
    )


def _submodule_checker_config_list_collect(
    project_root: Path,
    submodule_name_by_path_map: Mapping[str, str],
    checker_config_list: list[ProjectStandardCheckerConfig],
    execution_error_list: list[ProjectStandardExecutionError],
) -> None:
    """Collect host-conformance manifests from exact direct submodule checkouts.

    Args:
        project_root: Exact consumer repository root.
        submodule_name_by_path_map: Direct submodule names keyed by relative path.
        checker_config_list: Mutable normalized checker destination.
        execution_error_list: Mutable deterministic error destination.
    """

    for submodule_relative_path, submodule_name in submodule_name_by_path_map.items():
        owner = f"submodule:{submodule_name}"
        owner_root = (project_root / submodule_relative_path).resolve()
        manifest_path = owner_root / "project-standard-check.toml"
        if not manifest_path.is_file():
            continue
        try:
            checker_config_list.extend(
                _manifest_checker_config_list_get(
                    expected_owner=owner,
                    manifest_path=manifest_path,
                    owner_repository_path=submodule_relative_path,
                    owner_root=owner_root,
                )
            )
        except ValueError as error:
            execution_error_list.append(ProjectStandardExecutionError(id="<manifest>", message=str(error), owner=owner))


def _worktree_status_get(project_root: Path) -> str:
    """Return Git-visible target worktree state for mutation detection.

    Args:
        project_root: Exact consumer repository root.

    Returns:
        Porcelain status including direct-submodule state.
    """

    return git_output_get(
        project_root,
        ["status", "--porcelain=v1", "-z", "--ignore-submodules=none", "--untracked-files=all"],
    )


def main() -> int:
    """Run all applicable checks and return the canonical aggregate exit code.

    Returns:
        Zero for conformance, one for findings, or two for execution errors.
    """

    args = _args_parse()
    try:
        project_root = _project_root_get(args.project_root)
    except ValueError as error:
        _result_print(
            checker_count=0,
            execution_error_list=[
                ProjectStandardExecutionError(id="<project-root>", message=str(error), owner=DISTRIBUTION_NAME)
            ],
            finding_list=[],
            scope=args.scope,
        )
        return 2
    initial_worktree_status = _worktree_status_get(project_root)
    submodule_name_by_path_map = submodule_name_by_path_map_get(project_root)
    all_path_list = project_relpath_list_get(project_root, scope="all")
    changed_path_list = project_relpath_list_get(project_root, scope="changed")
    checker_config_list: list[ProjectStandardCheckerConfig] = []
    execution_error_list: list[ProjectStandardExecutionError] = []
    finding_list: list[ProjectStandardFinding] = []
    _capability_checker_config_list_collect(project_root, checker_config_list, execution_error_list)
    _submodule_checker_config_list_collect(
        project_root,
        submodule_name_by_path_map,
        checker_config_list,
        execution_error_list,
    )
    checker_config_list = _checker_config_list_dedupe(checker_config_list, execution_error_list)
    checker_count = 0
    for checker_config in checker_config_list:
        if not _should_checker_run(changed_path_list, checker_config, args.scope):
            continue
        checker_count += 1
        path_list = _checker_path_list_get(
            all_path_list=all_path_list,
            changed_path_list=changed_path_list,
            checker_config=checker_config,
            scope=args.scope,
            submodule_name_by_path_map=submodule_name_by_path_map,
        )
        try:
            finding_list.extend(
                _checker_finding_list_get(
                    checker_config=checker_config,
                    path_list=path_list,
                    project_root=project_root,
                    scope=args.scope,
                )
            )
        except ValueError as error:
            execution_error_list.append(
                ProjectStandardExecutionError(
                    id=checker_config["id"],
                    message=str(error),
                    owner=checker_config["owner"],
                )
            )
    if _worktree_status_get(project_root) != initial_worktree_status:
        execution_error_list.append(
            ProjectStandardExecutionError(
                id="<mutation>",
                message="Checker execution changed Git-visible target worktree state",
                owner=DISTRIBUTION_NAME,
            )
        )
    _result_print(
        checker_count=checker_count,
        execution_error_list=execution_error_list,
        finding_list=finding_list,
        scope=args.scope,
    )
    if execution_error_list:
        return 2
    return int(bool(finding_list))
