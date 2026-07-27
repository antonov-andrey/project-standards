#!/usr/bin/env python3
"""Validate the exact machine-facing subset of skill OpenAI metadata."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from project_standards.checker_protocol import checker_main
from project_standards.project_standard_model import ProjectStandardCheckerFinding, ProjectStandardRequest

SHORT_DESCRIPTION_MAX_LENGTH = 64
SHORT_DESCRIPTION_MIN_LENGTH = 25


def _mapping_get(
    payload: object,
    *,
    field_name: str,
    relative_path: str,
) -> tuple[dict[str, Any] | None, list[ProjectStandardCheckerFinding]]:
    """Return one optional mapping field or its exact finding.

    Args:
        payload: Untrusted parent mapping value.
        field_name: Child field name.
        relative_path: Metadata path for diagnostics.

    Returns:
        Optional child mapping and zero or one findings.
    """

    if not isinstance(payload, dict) or field_name not in payload:
        return None, []
    value = payload[field_name]
    if isinstance(value, dict):
        return value, []
    return None, [
        ProjectStandardCheckerFinding(
            message=f"agents/openai.yaml field {field_name} must be a mapping when present",
            path=relative_path,
        )
    ]


def _metadata_finding_list_get(
    *,
    metadata_path: Path,
    relative_path: str,
) -> list[ProjectStandardCheckerFinding]:
    """Return exact metadata findings for one current skill.

    Args:
        metadata_path: Absolute metadata file.
        relative_path: Repository-relative metadata path.

    Returns:
        Deterministically ordered findings for the file.
    """

    try:
        payload = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        return [
            ProjectStandardCheckerFinding(
                message=f"agents/openai.yaml must be readable YAML: {error}",
                path=relative_path,
            )
        ]
    if not isinstance(payload, dict):
        return [
            ProjectStandardCheckerFinding(
                message="agents/openai.yaml root must be a mapping",
                path=relative_path,
            )
        ]
    interface, finding_list = _mapping_get(
        payload,
        field_name="interface",
        relative_path=relative_path,
    )
    if interface is None:
        return finding_list
    skill_name = metadata_path.parents[1].name
    expected_invocation = f"${skill_name}"
    if "default_prompt" in interface:
        default_prompt = interface["default_prompt"]
        if not isinstance(default_prompt, str) or expected_invocation not in default_prompt:
            finding_list.append(
                ProjectStandardCheckerFinding(
                    message=f"interface.default_prompt must contain exact invocation {expected_invocation}",
                    path=relative_path,
                )
            )
    if "short_description" in interface:
        short_description = interface["short_description"]
        if not isinstance(short_description, str) or not (
            SHORT_DESCRIPTION_MIN_LENGTH <= len(short_description) <= SHORT_DESCRIPTION_MAX_LENGTH
        ):
            finding_list.append(
                ProjectStandardCheckerFinding(
                    message=(
                        "interface.short_description must contain from "
                        f"{SHORT_DESCRIPTION_MIN_LENGTH} through {SHORT_DESCRIPTION_MAX_LENGTH} characters"
                    ),
                    path=relative_path,
                )
            )
    return finding_list


def _finding_list_get(request: ProjectStandardRequest) -> list[ProjectStandardCheckerFinding]:
    """Return exact findings for every selected skill metadata file.

    Args:
        request: Validated checker process request.

    Returns:
        Metadata findings in request path order.
    """

    project_root = Path(request["project_root"])
    finding_list: list[ProjectStandardCheckerFinding] = []
    for relative_path in request["path_list"]:
        metadata_path = project_root / relative_path
        if not metadata_path.is_file():
            continue
        finding_list.extend(
            _metadata_finding_list_get(
                metadata_path=metadata_path,
                relative_path=relative_path,
            )
        )
    return finding_list


def main() -> int:
    """Run the exact skill metadata checker.

    Returns:
        Canonical checker protocol exit code.
    """

    return checker_main(_finding_list_get)


if __name__ == "__main__":
    raise SystemExit(main())
