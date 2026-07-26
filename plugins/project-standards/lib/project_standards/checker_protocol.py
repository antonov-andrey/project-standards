"""Versioned process protocol used by project-standard checker scripts."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
from pathlib import Path
import sys

from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

PROTOCOL_VERSION = 1
REQUEST_FIELD_SET = {"path_list", "project_root", "protocol_version", "scope"}


def _args_parse() -> argparse.Namespace:
    """Parse the checker process command line.

    Returns:
        Empty checker argument namespace.
    """

    return argparse.ArgumentParser(description=__doc__).parse_args()


def _checker_request_get() -> ProjectStandardRequest:
    """Read and validate one exact checker request from standard input.

    Returns:
        Validated process request.

    Raises:
        ValueError: Input is malformed or violates protocol version one.
    """

    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid checker request JSON: {error}") from error
    if not isinstance(payload, dict) or set(payload) != REQUEST_FIELD_SET:
        raise ValueError("Checker request must contain exactly path_list, project_root, protocol_version, and scope")
    if payload["protocol_version"] != PROTOCOL_VERSION:
        raise ValueError(f"Unsupported checker protocol version: {payload['protocol_version']!r}")
    project_root = payload["project_root"]
    if not isinstance(project_root, str) or not project_root:
        raise ValueError("Checker project_root must be one non-empty string")
    root_path = Path(project_root)
    if not root_path.is_absolute() or root_path.resolve() != root_path:
        raise ValueError("Checker project_root must be one canonical absolute path")
    scope = payload["scope"]
    if scope not in {"all", "changed"}:
        raise ValueError("Checker scope must be all or changed")
    path_list = payload["path_list"]
    if not isinstance(path_list, list) or any(not isinstance(path, str) for path in path_list):
        raise ValueError("Checker path_list must contain only strings")
    if path_list != sorted(set(path_list)):
        raise ValueError("Checker path_list must be sorted and unique")
    for relative_path in path_list:
        path = Path(relative_path)
        if not relative_path or path.is_absolute() or ".." in path.parts or path.as_posix() != relative_path:
            raise ValueError(f"Checker path is not one canonical relative POSIX path: {relative_path!r}")
    return ProjectStandardRequest(
        path_list=path_list,
        project_root=project_root,
        protocol_version=PROTOCOL_VERSION,
        scope=scope,
    )


def _checker_result_write(finding_list: list[ProjectStandardCheckerFinding]) -> int:
    """Validate, sort, and write checker-owned findings as JSON Lines.

    Args:
        finding_list: Findings produced by one owner-local checker.

    Returns:
        Zero when findings are empty, otherwise one.

    Raises:
        ValueError: One finding violates the process protocol.
    """

    normalized_finding_list: list[ProjectStandardCheckerFinding] = []
    for finding in finding_list:
        if not isinstance(finding, dict) or set(finding) not in (
            {"message", "path"},
            {"line", "message", "path"},
        ):
            raise ValueError("Checker finding contains unsupported fields")
        path_text = finding["path"]
        message = finding["message"]
        if not isinstance(path_text, str) or not path_text:
            raise ValueError("Checker finding path must be one non-empty string")
        path = Path(path_text)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != path_text:
            raise ValueError(f"Checker finding path is not canonical and relative: {path_text!r}")
        if not isinstance(message, str) or not message:
            raise ValueError("Checker finding message must be one non-empty string")
        if "line" in finding and (not isinstance(finding["line"], int) or finding["line"] <= 0):
            raise ValueError("Checker finding line must be one positive integer")
        normalized_finding_list.append(finding)
    normalized_finding_list.sort(
        key=lambda finding: (
            finding["path"],
            finding.get("line", 0),
            finding["message"],
        )
    )
    for finding in normalized_finding_list:
        print(json.dumps(finding, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return int(bool(normalized_finding_list))


def checker_main(
    finding_list_get: Callable[[ProjectStandardRequest], list[ProjectStandardCheckerFinding]],
) -> int:
    """Execute one checker through the canonical process boundary.

    Args:
        finding_list_get: Owner-local checker implementation.

    Returns:
        Protocol exit code for success, findings, or execution error.
    """

    _args_parse()
    try:
        request = _checker_request_get()
        finding_list = finding_list_get(request)
        return _checker_result_write(finding_list)
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 2
