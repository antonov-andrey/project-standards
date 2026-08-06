#!/usr/bin/env python3
"""Run opt-in model-based activation and output evaluations for skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import re
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING_EFFORT = "max"
CORPUS_SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 2
WORKING_DIRECTORY_MODE_SET = {"same-branch", "synchronized-main"}

_PLUGIN_IDENTITY_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SEMVER_PATTERN = re.compile(
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\."
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)

_GENERATION_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["activated_skill_list", "response"],
    "properties": {
        "activated_skill_list": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "response": {"type": "string", "minLength": 1},
    },
}

_JUDGE_OUTPUT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["invariant_result_list"],
    "properties": {
        "invariant_result_list": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "passed", "reason"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "passed": {"type": "boolean"},
                    "reason": {"type": "string", "minLength": 1},
                },
            },
        }
    },
}


class SkillBehaviorEvalError(RuntimeError):
    """Report an invalid corpus, model result, or Codex execution."""


@dataclass(frozen=True, slots=True)
class SemanticInvariant:
    """Define one semantic property required from the generated response."""

    id: str
    text: str


@dataclass(frozen=True, slots=True)
class SkillBehaviorCase:
    """Store one resolved activation and output-evaluation scenario."""

    corpus_path: Path
    expected_skill_list: tuple[str, ...]
    forbidden_skill_list: tuple[str, ...]
    id: str
    prompt: str
    semantic_invariant_list: tuple[SemanticInvariant, ...]
    suite: str
    working_directory: Path


@dataclass(frozen=True, slots=True)
class ModelInvocationConfig:
    """Store one immutable Codex model invocation configuration."""

    codex_bin: str
    model: str
    reasoning_effort: str


@dataclass(frozen=True, slots=True)
class CodexUsage:
    """Preserve the exact token counters exposed by one Codex turn."""

    cached_input_tokens: int
    cache_write_input_tokens: int
    input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int

    def __post_init__(self) -> None:
        """Require exact non-negative token counters with valid subset relations."""

        for field_name in (
            "cached_input_tokens",
            "cache_write_input_tokens",
            "input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SkillBehaviorEvalError(f"Codex usage {field_name} must be a non-negative integer")
        if self.cached_input_tokens > self.input_tokens:
            raise SkillBehaviorEvalError("Codex usage cached_input_tokens cannot exceed input_tokens")
        if self.cache_write_input_tokens > self.input_tokens:
            raise SkillBehaviorEvalError("Codex usage cache_write_input_tokens cannot exceed input_tokens")
        if self.reasoning_output_tokens > self.output_tokens:
            raise SkillBehaviorEvalError("Codex usage reasoning_output_tokens cannot exceed output_tokens")

    def add(self, other: CodexUsage) -> CodexUsage:
        """Add each exact counter independently.

        Args:
            other: Another directly exposed Codex usage value.

        Returns:
            The deterministic counter-wise aggregate.
        """

        return CodexUsage(
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            cache_write_input_tokens=self.cache_write_input_tokens + other.cache_write_input_tokens,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_output_tokens=self.reasoning_output_tokens + other.reasoning_output_tokens,
        )

    @classmethod
    def from_payload(cls, payload: object, *, context: str) -> CodexUsage:
        """Parse one exact Codex `turn.completed.usage` object.

        Args:
            payload: Candidate usage payload.
            context: Diagnostic event location.

        Returns:
            The validated exact usage counters.
        """

        expected_key_set = {
            "cached_input_tokens",
            "cache_write_input_tokens",
            "input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
        }
        if not isinstance(payload, dict) or set(payload) != expected_key_set:
            raise SkillBehaviorEvalError(f"{context}: Codex usage has another shape")
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class ModelInvocationResult:
    """Carry one structured response and its directly exposed turn usage."""

    payload: dict[str, Any]
    usage: CodexUsage


@dataclass(frozen=True, slots=True)
class SemanticInvariantResult:
    """Store one judge verdict."""

    id: str
    passed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class SkillBehaviorCaseResult:
    """Store complete activation and semantic results for one case."""

    activated_skill_list: tuple[str, ...]
    codex_usage_generation: CodexUsage
    codex_usage_judge: CodexUsage
    forbidden_activated_skill_list: tuple[str, ...]
    id: str
    missing_expected_skill_list: tuple[str, ...]
    passed: bool
    response: str
    semantic_invariant_result_list: tuple[SemanticInvariantResult, ...]
    suite: str


ModelCall = Callable[[str, Path, dict[str, Any], ModelInvocationConfig], ModelInvocationResult]


def _positive_int_get(value: str) -> int:
    """Parse one positive integer CLI value.

    Args:
        value: Candidate value.

    Returns:
        One positive integer CLI value.
    """

    parsed_value = int(value)
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed_value


def _argument_parser_get() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns:
        The command-line parser.
    """

    parser = argparse.ArgumentParser(
        description="Run opt-in GPT-5.6 Sol skill activation and semantic output evaluations.",
    )
    parser.add_argument(
        "--corpus",
        action="append",
        dest="corpus_path_list",
        required=True,
        type=Path,
        help="Path to one versioned skill behavior corpus; repeat for multiple providers.",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_id_list",
        default=[],
        help="Run only one exact case id; repeat to select multiple cases.",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex CLI executable.",
    )
    parser.add_argument(
        "--concurrency",
        default=4,
        type=_positive_int_get,
        help="Maximum concurrent cases; generation and judging remain ordered inside each case. Default: 4.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Validate corpora and list cases without model calls.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Target model for generation and independent judging; default: {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--plugin-marketplace",
        action="append",
        dest="plugin_marketplace_path_list",
        default=[],
        type=Path,
        help=(
            "Exact local plugin-marketplace root whose selected sources must match the server-prepared "
            "standard Codex home; repeat for multiple providers. Requires at least one --plugin."
        ),
    )
    parser.add_argument(
        "--plugin",
        action="append",
        dest="plugin_selector_list",
        default=[],
        help=(
            "Exact plugin selector NAME@MARKETPLACE to verify before evaluation; repeat as needed. "
            "Requires at least one --plugin-marketplace."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON result path. No result file is written when omitted.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh", "max", "ultra"),
        default=DEFAULT_REASONING_EFFORT,
        help=f"Reasoning effort for both model passes; default: {DEFAULT_REASONING_EFFORT}.",
    )
    return parser


def _exact_key_set_validate(
    payload: dict[str, Any],
    *,
    allowed_key_set: set[str],
    context: str,
    required_key_set: set[str],
) -> None:
    """Validate exact required and allowed object keys.

    Args:
        payload: Structured operation payload.
        allowed_key_set: Unique allowed key values.
        context: Context.
        required_key_set: Unique required key values.
    """

    missing_key_set = required_key_set - set(payload)
    unknown_key_set = set(payload) - allowed_key_set
    if missing_key_set:
        raise SkillBehaviorEvalError(f"{context}: missing fields: {', '.join(sorted(missing_key_set))}")
    if unknown_key_set:
        raise SkillBehaviorEvalError(f"{context}: unknown fields: {', '.join(sorted(unknown_key_set))}")


def _non_empty_string_get(payload: dict[str, Any], *, context: str, field_name: str) -> str:
    """Return one validated non-empty string field.

    Args:
        payload: Structured operation payload.
        context: Context.
        field_name: Field name.

    Returns:
        One validated non-empty string field.
    """

    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise SkillBehaviorEvalError(f"{context}.{field_name}: expected non-empty string")
    return value.strip()


def _string_tuple_get(payload: dict[str, Any], *, context: str, field_name: str) -> tuple[str, ...]:
    """Return one validated unique string-list field.

    Args:
        payload: Structured operation payload.
        context: Context.
        field_name: Field name.

    Returns:
        One validated unique string-list field.
    """

    value = payload.get(field_name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise SkillBehaviorEvalError(f"{context}.{field_name}: expected string list")
    normalized_value_list = [item.strip() for item in value]
    if len(normalized_value_list) != len(set(normalized_value_list)):
        raise SkillBehaviorEvalError(f"{context}.{field_name}: duplicate values are forbidden")
    return tuple(normalized_value_list)


def _semantic_invariant_tuple_get(
    payload: dict[str, Any],
    *,
    context: str,
) -> tuple[SemanticInvariant, ...]:
    """Return validated semantic invariants.

    Args:
        payload: Structured operation payload.
        context: Context.

    Returns:
        The validated semantic invariants.
    """

    raw_invariant_list = payload.get("semantic_invariant_list")
    if not isinstance(raw_invariant_list, list) or not raw_invariant_list:
        raise SkillBehaviorEvalError(f"{context}.semantic_invariant_list: expected non-empty object list")
    invariant_list: list[SemanticInvariant] = []
    for index, raw_invariant in enumerate(raw_invariant_list):
        invariant_context = f"{context}.semantic_invariant_list[{index}]"
        if not isinstance(raw_invariant, dict):
            raise SkillBehaviorEvalError(f"{invariant_context}: expected object")
        _exact_key_set_validate(
            raw_invariant,
            allowed_key_set={"id", "text"},
            context=invariant_context,
            required_key_set={"id", "text"},
        )
        invariant_list.append(
            SemanticInvariant(
                id=_non_empty_string_get(raw_invariant, context=invariant_context, field_name="id"),
                text=_non_empty_string_get(raw_invariant, context=invariant_context, field_name="text"),
            )
        )
    invariant_id_list = [invariant.id for invariant in invariant_list]
    if len(invariant_id_list) != len(set(invariant_id_list)):
        raise SkillBehaviorEvalError(f"{context}.semantic_invariant_list: duplicate ids are forbidden")
    return tuple(invariant_list)


def _git_output_get(repository_root: Path, argument_list: list[str], *, context: str) -> str:
    """Return checked Git output for one repository-local discovery command.

    Args:
        repository_root: Repository root.
        argument_list: Exact command arguments.
        context: Context.

    Returns:
        The checked Git output for one repository-local discovery command.
    """

    environment_by_name_map = os.environ.copy()
    for variable_name in (
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_CONFIG",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_SYSTEM",
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_NAMESPACE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_PREFIX",
        "GIT_QUARANTINE_PATH",
        "GIT_WORK_TREE",
    ):
        environment_by_name_map.pop(variable_name, None)
    for variable_name in list(environment_by_name_map):
        if variable_name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            environment_by_name_map.pop(variable_name)
    environment_by_name_map.pop("GIT_LITERAL_PATHSPECS", None)
    environment_by_name_map["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(
        ["git", "-C", str(repository_root), *argument_list],
        capture_output=True,
        check=False,
        encoding="utf-8",
        env=environment_by_name_map,
        errors="surrogateescape",
    )
    if result.returncode != 0:
        raise SkillBehaviorEvalError(f"{context}: Git command failed: {result.stderr.strip()}")
    return result.stdout


def _git_repository_root_get(path: Path, *, context: str) -> Path:
    """Return the exact worktree root containing one existing directory.

    Args:
        path: Exact filesystem path.
        context: Context.

    Returns:
        The exact worktree root containing one existing directory.
    """

    root_text = _git_output_get(
        path,
        ["rev-parse", "--show-toplevel"],
        context=context,
    ).strip()
    if not root_text:
        raise SkillBehaviorEvalError(f"{context}: Git returned an empty repository root")
    return Path(root_text).resolve()


def _git_common_directory_get(repository_root: Path, *, context: str) -> Path:
    """Return one repository's canonical common Git administration directory.

    Args:
        repository_root: Repository root.
        context: Context.

    Returns:
        One repository's canonical common Git administration directory.
    """

    common_directory = Path(
        _git_output_get(
            repository_root,
            ["rev-parse", "--git-common-dir"],
            context=context,
        ).strip()
    )
    if not common_directory.is_absolute():
        common_directory = repository_root / common_directory
    return common_directory.resolve()


def _registered_worktree_root_validate(
    raw_worktree_path: str,
    *,
    expected_branch_ref: str | None,
    expected_common_directory: Path,
    context: str,
) -> Path:
    """Return one physical registered worktree after re-proving its Git identity.

    Args:
        raw_worktree_path: Exact filesystem path for raw worktree.
        expected_branch_ref: Expected branch ref.
        expected_common_directory: Expected common directory.
        context: Context.

    Returns:
        One physical registered worktree after re-proving its Git identity.
    """

    worktree_path = Path(raw_worktree_path)
    if worktree_path.is_symlink() or not worktree_path.is_dir():
        raise SkillBehaviorEvalError(f"{context}: registered worktree is not one physical directory: {worktree_path}")
    absolute_worktree_path = Path(os.path.abspath(worktree_path))
    resolved_worktree_root = worktree_path.resolve()
    if absolute_worktree_path != resolved_worktree_root:
        raise SkillBehaviorEvalError(f"{context}: registered worktree path traverses a symbolic link: {worktree_path}")
    if (
        _git_repository_root_get(
            resolved_worktree_root,
            context=f"{context}: cannot re-prove registered worktree root",
        )
        != resolved_worktree_root
        or _git_common_directory_get(
            resolved_worktree_root,
            context=f"{context}: cannot re-prove registered worktree owner",
        )
        != expected_common_directory
    ):
        raise SkillBehaviorEvalError(f"{context}: registered worktree Git identity is inconsistent: {worktree_path}")
    if expected_branch_ref is not None:
        actual_branch_ref = _git_output_get(
            resolved_worktree_root,
            ["symbolic-ref", "--quiet", "HEAD"],
            context=f"{context}: registered worktree must use one branch",
        ).strip()
        if actual_branch_ref != expected_branch_ref:
            raise SkillBehaviorEvalError(
                f"{context}: registered worktree branch is inconsistent: " f"{resolved_worktree_root}"
            )
    return resolved_worktree_root


def _git_worktree_record_list_get(repository_root: Path, *, context: str) -> list[dict[str, str]]:
    """Return NUL-safe Git worktree records.

    Args:
        repository_root: Repository root.
        context: Context.

    Returns:
        NUL-delimited Git worktree records.
    """

    output = _git_output_get(
        repository_root,
        ["worktree", "list", "--porcelain", "-z"],
        context=context,
    )
    record_list: list[dict[str, str]] = []
    current_record: dict[str, str] = {}
    for item in [*output.split("\0"), ""]:
        if not item:
            if current_record:
                if "worktree" not in current_record:
                    raise SkillBehaviorEvalError(f"{context}: worktree record has no path")
                record_list.append(current_record)
                current_record = {}
            continue
        key, separator, value = item.partition(" ")
        if not separator:
            current_record[item] = ""
        else:
            current_record[key] = value
    if not record_list:
        raise SkillBehaviorEvalError(f"{context}: Git returned no worktree records")
    return record_list


def _working_directory_resolve(
    resolved_corpus_path: Path,
    working_directory_value: str,
    *,
    context: str,
    mode: str,
) -> Path:
    """Resolve one corpus directory under its declared Git revision policy.

    Args:
        resolved_corpus_path: Exact filesystem path for resolved corpus.
        working_directory_value: Working directory value.
        context: Context.
        mode: Mode.

    Returns:
        One corpus directory under its declared Git revision policy.
    """

    if mode not in WORKING_DIRECTORY_MODE_SET:
        raise SkillBehaviorEvalError(
            f"{context}: working_directory_mode must be one of: {', '.join(sorted(WORKING_DIRECTORY_MODE_SET))}"
        )

    raw_direct_candidate = resolved_corpus_path.parent / working_directory_value
    direct_candidate = raw_direct_candidate.resolve()
    try:
        source_repository_root = _git_repository_root_get(
            resolved_corpus_path.parent,
            context=f"{context}: cannot identify the corpus repository",
        )
    except SkillBehaviorEvalError:
        if direct_candidate.is_dir():
            return direct_candidate
        raise
    source_branch_ref = _git_output_get(
        source_repository_root,
        ["symbolic-ref", "--quiet", "HEAD"],
        context=f"{context}: corpus worktree must use one branch",
    ).strip()
    if not source_branch_ref.startswith("refs/heads/"):
        raise SkillBehaviorEvalError(f"{context}: corpus worktree has no local branch identity")
    if direct_candidate.is_dir() and mode == "same-branch":
        direct_repository_root = _git_repository_root_get(
            direct_candidate,
            context=f"{context}: direct target is not inside a Git worktree",
        )
        direct_branch_ref = _git_output_get(
            direct_repository_root,
            ["symbolic-ref", "--quiet", "HEAD"],
            context=f"{context}: direct target must use one branch",
        ).strip()
        if direct_branch_ref != source_branch_ref:
            raise SkillBehaviorEvalError(
                f"{context}: direct target branch {direct_branch_ref or '<detached>'} "
                f"does not match corpus branch {source_branch_ref}"
            )
        if Path(os.path.abspath(raw_direct_candidate)) != direct_candidate:
            raise SkillBehaviorEvalError(
                f"{context}: direct target path traverses a symbolic link: " f"{raw_direct_candidate}"
            )
        return direct_candidate

    source_worktree_record_list = _git_worktree_record_list_get(
        source_repository_root,
        context=f"{context}: cannot identify the corpus primary worktree",
    )
    source_common_directory = _git_common_directory_get(
        source_repository_root,
        context=f"{context}: cannot identify the corpus Git owner",
    )
    primary_repository_root = _registered_worktree_root_validate(
        source_worktree_record_list[0]["worktree"],
        expected_branch_ref=None,
        expected_common_directory=source_common_directory,
        context=f"{context}: corpus primary worktree",
    )
    try:
        corpus_relative_path = resolved_corpus_path.relative_to(source_repository_root)
    except ValueError as exc:
        raise SkillBehaviorEvalError(f"{context}: corpus path escapes its current worktree") from exc
    raw_primary_candidate = primary_repository_root / corpus_relative_path.parent / working_directory_value
    primary_candidate = raw_primary_candidate.resolve()
    if Path(os.path.abspath(raw_primary_candidate)) != primary_candidate:
        raise SkillBehaviorEvalError(
            f"{context}: primary-layout target path traverses a symbolic link: " f"{raw_primary_candidate}"
        )
    if not primary_candidate.is_dir():
        raise SkillBehaviorEvalError(
            f"{context}: not a directory in either the current or primary layout: {direct_candidate}"
        )
    target_primary_root = _git_repository_root_get(
        primary_candidate,
        context=f"{context}: target directory is not inside a Git repository",
    )
    try:
        target_relative_path = primary_candidate.relative_to(target_primary_root)
    except ValueError as exc:
        raise SkillBehaviorEvalError(f"{context}: target directory escapes its primary repository") from exc
    target_common_directory = _git_common_directory_get(
        target_primary_root,
        context=f"{context}: cannot identify target Git owner",
    )
    if mode == "synchronized-main":
        target_worktree_record_list = _git_worktree_record_list_get(
            target_primary_root,
            context=f"{context}: cannot inspect target worktrees",
        )
        canonical_main_root = _registered_worktree_root_validate(
            target_worktree_record_list[0]["worktree"],
            expected_branch_ref="refs/heads/main",
            expected_common_directory=target_common_directory,
            context=f"{context}: synchronized target main worktree",
        )
        if canonical_main_root != target_primary_root:
            raise SkillBehaviorEvalError(f"{context}: target path is not inside the canonical main worktree")
        if _git_output_get(
            canonical_main_root,
            ["status", "--porcelain"],
            context=f"{context}: cannot inspect target main state",
        ):
            raise SkillBehaviorEvalError(f"{context}: target main worktree is not clean")
        local_commit = _git_output_get(
            canonical_main_root,
            ["rev-parse", "HEAD"],
            context=f"{context}: cannot resolve target main commit",
        ).strip()
        upstream_commit = _git_output_get(
            canonical_main_root,
            ["rev-parse", "refs/remotes/origin/main"],
            context=f"{context}: cannot resolve target origin/main commit",
        ).strip()
        if local_commit != upstream_commit:
            raise SkillBehaviorEvalError(f"{context}: target main does not equal origin/main")
        return primary_candidate
    matching_worktree_root_list = []
    for record in _git_worktree_record_list_get(
        target_primary_root,
        context=f"{context}: cannot inspect target worktrees",
    ):
        if record.get("branch") != source_branch_ref:
            continue
        matching_worktree_root_list.append(
            _registered_worktree_root_validate(
                record["worktree"],
                expected_branch_ref=source_branch_ref,
                expected_common_directory=target_common_directory,
                context=f"{context}: same-branch target worktree",
            )
        )
    if len(matching_worktree_root_list) != 1:
        raise SkillBehaviorEvalError(
            f"{context}: expected exactly one target worktree on {source_branch_ref}, "
            f"found {len(matching_worktree_root_list)}"
        )
    same_branch_candidate = (matching_worktree_root_list[0] / target_relative_path).resolve()
    try:
        same_branch_candidate.relative_to(matching_worktree_root_list[0])
    except ValueError as exc:
        raise SkillBehaviorEvalError(
            f"{context}: same-branch target path escapes its worktree: " f"{same_branch_candidate}"
        ) from exc
    if (
        not same_branch_candidate.is_dir()
        or _git_repository_root_get(
            same_branch_candidate,
            context=f"{context}: cannot re-prove same-branch target path",
        )
        != matching_worktree_root_list[0]
    ):
        raise SkillBehaviorEvalError(f"{context}: same-branch target path is not a directory: {same_branch_candidate}")
    return same_branch_candidate


def _corpus_case_list_load(
    corpus_path: Path,
    *,
    selected_case_id_set: set[str] | None = None,
) -> list[SkillBehaviorCase]:
    """Load all case contracts while resolving only the selected runtime roots.

    Args:
        corpus_path: Exact filesystem path for corpus.
        selected_case_id_set: Unique selected case identity values.

    Returns:
        All case contracts with runtime roots resolved only for selected cases.
    """

    resolved_corpus_path = corpus_path.expanduser().resolve()
    try:
        payload = json.loads(resolved_corpus_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillBehaviorEvalError(f"{resolved_corpus_path}: cannot load corpus: {exc}") from exc
    if not isinstance(payload, dict):
        raise SkillBehaviorEvalError(f"{resolved_corpus_path}: corpus root must be an object")
    _exact_key_set_validate(
        payload,
        allowed_key_set={"case_list", "schema_version", "suite"},
        context=str(resolved_corpus_path),
        required_key_set={"case_list", "schema_version", "suite"},
    )
    if type(payload["schema_version"]) is not int or payload["schema_version"] != CORPUS_SCHEMA_VERSION:
        raise SkillBehaviorEvalError(
            f"{resolved_corpus_path}: schema_version must equal {CORPUS_SCHEMA_VERSION}, "
            f"got {payload['schema_version']!r}"
        )
    suite = _non_empty_string_get(payload, context=str(resolved_corpus_path), field_name="suite")
    raw_case_list = payload["case_list"]
    if not isinstance(raw_case_list, list) or not raw_case_list:
        raise SkillBehaviorEvalError(f"{resolved_corpus_path}.case_list: expected non-empty object list")

    case_list: list[SkillBehaviorCase] = []
    corpus_case_id_list: list[str] = []
    for index, raw_case in enumerate(raw_case_list):
        case_context = f"{resolved_corpus_path}.case_list[{index}]"
        if not isinstance(raw_case, dict):
            raise SkillBehaviorEvalError(f"{case_context}: expected object")
        _exact_key_set_validate(
            raw_case,
            allowed_key_set={
                "expected_skill_list",
                "forbidden_skill_list",
                "id",
                "prompt",
                "semantic_invariant_list",
                "working_directory",
                "working_directory_mode",
            },
            context=case_context,
            required_key_set={
                "expected_skill_list",
                "forbidden_skill_list",
                "id",
                "prompt",
                "semantic_invariant_list",
                "working_directory",
                "working_directory_mode",
            },
        )
        expected_skill_list = _string_tuple_get(
            raw_case,
            context=case_context,
            field_name="expected_skill_list",
        )
        forbidden_skill_list = _string_tuple_get(
            raw_case,
            context=case_context,
            field_name="forbidden_skill_list",
        )
        overlap_skill_set = set(expected_skill_list) & set(forbidden_skill_list)
        if overlap_skill_set:
            raise SkillBehaviorEvalError(
                f"{case_context}: expected and forbidden skills overlap: {', '.join(sorted(overlap_skill_set))}"
            )
        case_id = _non_empty_string_get(raw_case, context=case_context, field_name="id")
        corpus_case_id_list.append(case_id)
        working_directory_value = _non_empty_string_get(
            raw_case,
            context=case_context,
            field_name="working_directory",
        )
        working_directory_mode = _non_empty_string_get(
            raw_case,
            context=case_context,
            field_name="working_directory_mode",
        )
        selected = selected_case_id_set is None or bool({case_id, f"{suite}:{case_id}"} & selected_case_id_set)
        prompt = _non_empty_string_get(raw_case, context=case_context, field_name="prompt")
        semantic_invariant_list = _semantic_invariant_tuple_get(raw_case, context=case_context)
        if not selected:
            continue
        working_directory = _working_directory_resolve(
            resolved_corpus_path,
            working_directory_value,
            context=f"{case_context}.working_directory",
            mode=working_directory_mode,
        )
        case_list.append(
            SkillBehaviorCase(
                corpus_path=resolved_corpus_path,
                expected_skill_list=expected_skill_list,
                forbidden_skill_list=forbidden_skill_list,
                id=case_id,
                prompt=prompt,
                semantic_invariant_list=semantic_invariant_list,
                suite=suite,
                working_directory=working_directory,
            )
        )
    if len(corpus_case_id_list) != len(set(corpus_case_id_list)):
        raise SkillBehaviorEvalError(f"{resolved_corpus_path}: duplicate case ids are forbidden")
    return case_list


def _selected_case_list_get(
    *,
    case_id_list: Sequence[str],
    corpus_path_list: Sequence[Path],
) -> list[SkillBehaviorCase]:
    """Load corpora and apply exact case selection.

    Args:
        case_id_list: Ordered case identity values.
        corpus_path_list: Ordered corpus path values.

    Returns:
        Cases selected exactly from the declared corpora.
    """

    requested_case_id_set = set(case_id_list)
    case_list = [
        case
        for corpus_path in corpus_path_list
        for case in _corpus_case_list_load(
            corpus_path,
            selected_case_id_set=(requested_case_id_set or None),
        )
    ]
    qualified_id_list = [f"{case.suite}:{case.id}" for case in case_list]
    if len(qualified_id_list) != len(set(qualified_id_list)):
        raise SkillBehaviorEvalError("duplicate suite-qualified case ids are forbidden")
    if not case_id_list:
        return case_list
    selected_case_list = case_list
    matched_case_id_set = {
        requested_id
        for requested_id in requested_case_id_set
        if any(requested_id in {case.id, f"{case.suite}:{case.id}"} for case in selected_case_list)
    }
    unknown_case_id_set = requested_case_id_set - matched_case_id_set
    if unknown_case_id_set:
        raise SkillBehaviorEvalError(f"unknown case ids: {', '.join(sorted(unknown_case_id_set))}")
    return selected_case_list


def _generation_prompt_get(case: SkillBehaviorCase) -> str:
    """Build the isolated generation prompt for one case.

    Args:
        case: Case.

    Returns:
        The isolated generation prompt for one case.
    """

    return f"""This is a read-only skill behavior evaluation.

Treat the scenario below exactly as the user's request in the current repository. Use the normally applicable
project instructions and skills. Do not change files, create commits, push, deploy, or mutate external state.
Give the concise response or proposed approach that would be correct before implementation.

Return:
- `response`: that user-facing answer;
- `activated_skill_list`: exact provider-qualified skill names whose SKILL.md instructions you actually loaded and
  applied for this response. Use project-local skill names without a provider prefix.

Do not list merely available skills or skills considered but not activated.

Scenario:
{case.prompt}
"""


def _judge_prompt_get(
    *,
    case: SkillBehaviorCase,
    generation_payload: dict[str, Any],
) -> str:
    """Build an independent semantic judge prompt for one generated response.

    Args:
        case: Case.
        generation_payload: Generation payload.

    Returns:
        An independent semantic judge prompt for one generated response.
    """

    invariant_payload = [asdict(invariant) for invariant in case.semantic_invariant_list]
    return f"""Act as an independent semantic evaluator. Do not inspect files and do not improve the answer.

This judge evaluates a read-only behavior simulation. The candidate must not perform file, Git, deployment, or
external mutations. When an invariant describes a mutation from the real workflow, evaluate whether the response
correctly commits to that action for a real run; do not require or reward performing it in this simulation. A
response still fails when it omits, rejects, or changes the real workflow action rather than only deferring it here.

Evaluate whether the candidate response satisfies each invariant in substance. Do not use keyword, substring,
heading, or formatting checks. A claim passes only when the response's actual meaning meets the full invariant.
Return exactly one result for every invariant id, in the given order.

User scenario:
{case.prompt}

Candidate activated skills:
{json.dumps(generation_payload["activated_skill_list"], ensure_ascii=False)}

Candidate response:
{generation_payload["response"]}

Semantic invariants:
{json.dumps(invariant_payload, ensure_ascii=False, indent=2)}
"""


def _codex_usage_get(event_jsonl: str) -> CodexUsage:
    """Return exact usage from one structured Codex JSONL invocation.

    Args:
        event_jsonl: Direct stdout from `codex exec --json`.

    Returns:
        The sole completed-turn usage value.
    """

    completed_usage_list: list[CodexUsage] = []
    for index, event_text in enumerate(event_jsonl.splitlines()):
        try:
            event = json.loads(event_text)
        except json.JSONDecodeError as exc:
            raise SkillBehaviorEvalError(f"Codex JSONL event[{index}] is invalid JSON") from exc
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise SkillBehaviorEvalError(f"Codex JSONL event[{index}] has another shape")
        if event["type"] == "turn.completed":
            if set(event) != {"type", "usage"}:
                raise SkillBehaviorEvalError(f"Codex JSONL event[{index}] turn completion has another shape")
            completed_usage_list.append(
                CodexUsage.from_payload(event["usage"], context=f"Codex JSONL event[{index}].usage")
            )
    if len(completed_usage_list) != 1:
        raise SkillBehaviorEvalError("Codex JSONL must contain exactly one turn.completed usage event")
    return completed_usage_list[0]


def _codex_payload_get(
    prompt: str,
    working_directory: Path,
    output_schema: dict[str, Any],
    invocation_config: ModelInvocationConfig,
) -> ModelInvocationResult:
    """Invoke Codex once and return its structured payload and exact usage.

    Args:
        prompt: Prompt.
        working_directory: Working directory.
        output_schema: Output schema.
        invocation_config: Invocation config.

    Returns:
        Structured final response and direct `turn.completed.usage` counters.
    """

    with tempfile.TemporaryDirectory(prefix="skill-behavior-eval-") as temporary_directory_value:
        temporary_directory = Path(temporary_directory_value)
        output_path = temporary_directory / "output.json"
        schema_path = temporary_directory / "schema.json"
        schema_path.write_text(json.dumps(output_schema, ensure_ascii=False), encoding="utf-8")
        command = [
            invocation_config.codex_bin,
            "exec",
            "--json",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--model",
            invocation_config.model,
            "--config",
            f'model_reasoning_effort="{invocation_config.reasoning_effort}"',
            "--cd",
            str(working_directory),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-",
        ]
        environment_by_name_map = _standard_codex_process_environment_get()
        try:
            completed_process = subprocess.run(
                command,
                check=False,
                capture_output=True,
                env=environment_by_name_map,
                input=prompt,
                text=True,
            )
        except OSError as exc:
            raise SkillBehaviorEvalError(f"Codex invocation failed: {exc}") from exc
        if completed_process.returncode != 0:
            stderr_tail = completed_process.stderr[-4000:].strip()
            stdout_tail = completed_process.stdout[-4000:].strip()
            raise SkillBehaviorEvalError(
                f"Codex exited with {completed_process.returncode}; stdout={stdout_tail!r}; stderr={stderr_tail!r}"
            )
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SkillBehaviorEvalError(f"Codex returned invalid structured output: {exc}") from exc
    if not isinstance(payload, dict):
        raise SkillBehaviorEvalError("Codex structured output must be an object")
    return ModelInvocationResult(
        payload=payload,
        usage=_codex_usage_get(completed_process.stdout),
    )


def _standard_codex_process_environment_get(
    environment_by_name_map: dict[str, str] | None = None,
    *,
    os_user_home: Path | None = None,
) -> dict[str, str]:
    """Return the unchanged standard-home environment for one Codex process."""

    environment = dict(os.environ if environment_by_name_map is None else environment_by_name_map)
    user_home = Path(pwd.getpwuid(os.getuid()).pw_dir) if os_user_home is None else os_user_home
    try:
        resolved_user_home = user_home.resolve(strict=True)
    except OSError as exc:
        raise SkillBehaviorEvalError("the current OS user home is unavailable") from exc
    if not resolved_user_home.is_dir() or str(resolved_user_home) != environment.get("HOME"):
        raise SkillBehaviorEvalError("HOME must equal the current OS user home")
    if "CODEX_HOME" in environment:
        raise SkillBehaviorEvalError("CODEX_HOME must remain unset")
    if not (resolved_user_home / ".codex").is_dir():
        raise SkillBehaviorEvalError("server bootstrap must prepare the standard Codex home")
    return environment


def _plugin_file_sha256_by_relative_path_map_get(root: Path) -> dict[str, str]:
    """Return one exact source-file snapshot for a plugin tree."""

    file_sha256_by_relative_path_map: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative_path = path.relative_to(root)
        if "__pycache__" in relative_path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise SkillBehaviorEvalError(f"plugin tree contains a symbolic link: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise SkillBehaviorEvalError(f"plugin tree contains a non-file entry: {path}")
        file_sha256_by_relative_path_map[relative_path.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return file_sha256_by_relative_path_map


def _preinstalled_plugin_source_binding_validate(
    *,
    case_list: Sequence[SkillBehaviorCase],
    marketplace_path_list: Sequence[Path],
    plugin_selector_list: Sequence[str],
    standard_codex_home: Path,
) -> dict[str, str]:
    """Require server-prepared plugins to equal the declared local sources.

    Args:
        case_list: Ordered selected behavior cases.
        marketplace_path_list: Ordered marketplace path values.
        plugin_selector_list: Ordered plugin selector values.
        standard_codex_home: Current OS user's standard Codex home.

    Returns:
        Exact validated source selector by provider.
    """

    if bool(marketplace_path_list) != bool(plugin_selector_list):
        raise SkillBehaviorEvalError(
            "--plugin-marketplace and --plugin must be supplied together so the evaluated source is explicit"
        )
    if not marketplace_path_list:
        raise SkillBehaviorEvalError("every model run requires explicit --plugin-marketplace and --plugin binding")

    normalized_plugin_selector_list = _plugin_selector_tuple_normalize(plugin_selector_list)
    plugin_selector_by_name_map = _plugin_selector_by_name_map_get(normalized_plugin_selector_list)
    _required_plugin_source_binding_validate(case_list, plugin_selector_by_name_map)

    raw_cache_root = standard_codex_home / "plugins/cache"
    try:
        resolved_cache_root = raw_cache_root.resolve(strict=True)
    except OSError as exc:
        raise SkillBehaviorEvalError("the standard Codex plugin cache root is unavailable") from exc
    if (
        Path(os.path.abspath(raw_cache_root)) != resolved_cache_root
        or raw_cache_root.is_symlink()
        or not resolved_cache_root.is_dir()
    ):
        raise SkillBehaviorEvalError("the standard Codex plugin cache root must be one physical directory")

    resolved_marketplace_path_list: list[Path] = []
    plugin_source_path_by_name_by_marketplace_name_map: dict[str, dict[str, Path]] = {}
    for marketplace_path in marketplace_path_list:
        resolved_marketplace_path = marketplace_path.expanduser().resolve()
        marketplace_manifest_path = resolved_marketplace_path / ".agents/plugins/marketplace.json"
        if not marketplace_manifest_path.is_file():
            raise SkillBehaviorEvalError(
                f"plugin marketplace has no .agents/plugins/marketplace.json: {resolved_marketplace_path}"
            )
        if resolved_marketplace_path in resolved_marketplace_path_list:
            raise SkillBehaviorEvalError(f"duplicate plugin marketplace: {resolved_marketplace_path}")
        resolved_marketplace_path_list.append(resolved_marketplace_path)

        try:
            marketplace_payload = json.loads(marketplace_manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SkillBehaviorEvalError(
                f"plugin marketplace manifest is unavailable or invalid: {marketplace_manifest_path}: {exc}"
            ) from exc
        if not isinstance(marketplace_payload, dict):
            raise SkillBehaviorEvalError(f"plugin marketplace manifest must be an object: {marketplace_manifest_path}")
        marketplace_name = marketplace_payload.get("name")
        plugin_list = marketplace_payload.get("plugins")
        if (
            not isinstance(marketplace_name, str)
            or not marketplace_name.strip()
            or not isinstance(plugin_list, list)
            or any(
                not isinstance(plugin, dict) or not isinstance(plugin.get("name"), str) or not plugin["name"].strip()
                for plugin in plugin_list
            )
        ):
            raise SkillBehaviorEvalError(
                f"plugin marketplace manifest has no usable name/plugin inventory: {marketplace_manifest_path}"
            )
        normalized_marketplace_name = marketplace_name
        _plugin_identity_validate(normalized_marketplace_name, label="plugin marketplace name")
        if normalized_marketplace_name in plugin_source_path_by_name_by_marketplace_name_map:
            raise SkillBehaviorEvalError(f"duplicate plugin marketplace name: {normalized_marketplace_name}")
        plugin_source_path_by_name_map: dict[str, Path] = {}
        for plugin in plugin_list:
            plugin_name = plugin["name"]
            _plugin_identity_validate(plugin_name, label="plugin name")
            if plugin_name in plugin_source_path_by_name_map:
                raise SkillBehaviorEvalError(
                    f"duplicate plugin name in marketplace {normalized_marketplace_name}: " f"{plugin_name}"
                )
            source = plugin.get("source")
            if (
                not isinstance(source, dict)
                or source.get("source") != "local"
                or not isinstance(source.get("path"), str)
                or not source["path"].strip()
            ):
                raise SkillBehaviorEvalError(
                    f"plugin source must be one local path in its provided marketplace: "
                    f"{plugin_name}@{normalized_marketplace_name}"
                )
            raw_plugin_source_path = resolved_marketplace_path / source["path"]
            plugin_source_path = raw_plugin_source_path.resolve()
            try:
                plugin_source_path.relative_to(resolved_marketplace_path)
            except ValueError as exc:
                raise SkillBehaviorEvalError(
                    f"plugin source escapes its provided marketplace: " f"{plugin_name}@{normalized_marketplace_name}"
                ) from exc
            if Path(os.path.abspath(raw_plugin_source_path)) != plugin_source_path or not plugin_source_path.is_dir():
                raise SkillBehaviorEvalError(
                    f"plugin source must be one physical directory in its provided marketplace: "
                    f"{plugin_name}@{normalized_marketplace_name}"
                )
            plugin_source_path_by_name_map[plugin_name] = plugin_source_path
        plugin_source_path_by_name_by_marketplace_name_map[normalized_marketplace_name] = plugin_source_path_by_name_map

    for plugin_selector in normalized_plugin_selector_list:
        plugin_name, marketplace_name = plugin_selector.split("@", 1)
        if marketplace_name not in plugin_source_path_by_name_by_marketplace_name_map:
            raise SkillBehaviorEvalError(f"plugin selector references an unprovided marketplace: {plugin_selector}")
        if plugin_name not in plugin_source_path_by_name_by_marketplace_name_map[marketplace_name]:
            raise SkillBehaviorEvalError(f"plugin selector is absent from its provided marketplace: {plugin_selector}")
        plugin_source_path = plugin_source_path_by_name_by_marketplace_name_map[marketplace_name][plugin_name]
        plugin_manifest_path = plugin_source_path / ".codex-plugin/plugin.json"
        try:
            plugin_manifest = json.loads(plugin_manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SkillBehaviorEvalError(f"plugin manifest is unavailable or invalid: {plugin_manifest_path}") from exc
        if not isinstance(plugin_manifest, dict) or plugin_manifest.get("name") != plugin_name:
            raise SkillBehaviorEvalError(f"plugin manifest identity differs from its selector: {plugin_selector}")
        plugin_version = plugin_manifest.get("version")
        if not isinstance(plugin_version, str) or _SEMVER_PATTERN.fullmatch(plugin_version) is None:
            raise SkillBehaviorEvalError(f"plugin manifest version must be strict SemVer: {plugin_selector}")
        raw_cached_plugin_path = resolved_cache_root / marketplace_name / plugin_name / plugin_version
        try:
            cached_plugin_path = raw_cached_plugin_path.resolve(strict=True)
            cached_plugin_path.relative_to(resolved_cache_root)
        except (OSError, ValueError) as exc:
            raise SkillBehaviorEvalError(f"server bootstrap did not prepare the selected plugin: {plugin_selector}")
        if (
            Path(os.path.abspath(raw_cached_plugin_path)) != cached_plugin_path
            or raw_cached_plugin_path.is_symlink()
            or not cached_plugin_path.is_dir()
        ):
            raise SkillBehaviorEvalError(
                f"server-prepared plugin cache must be one physical directory below the standard cache root: "
                f"{plugin_selector}"
            )
        if _plugin_file_sha256_by_relative_path_map_get(
            plugin_source_path
        ) != _plugin_file_sha256_by_relative_path_map_get(cached_plugin_path):
            raise SkillBehaviorEvalError(f"server-prepared plugin differs from its declared source: {plugin_selector}")
    return plugin_selector_by_name_map


def _plugin_selector_tuple_normalize(
    plugin_selector_list: Sequence[str],
) -> tuple[str, ...]:
    """Validate and normalize exact plugin selectors before source binding.

    Args:
        plugin_selector_list: Ordered plugin selector values.

    Returns:
        Values in deterministic immutable order.
    """

    normalized_plugin_selector_list = tuple(plugin_selector_list)
    for selector in normalized_plugin_selector_list:
        if not isinstance(selector, str) or selector.count("@") != 1:
            raise SkillBehaviorEvalError("every --plugin must use exact NAME@MARKETPLACE form")
        plugin_name, marketplace_name = selector.split("@", 1)
        _plugin_identity_validate(plugin_name, label="plugin selector name")
        _plugin_identity_validate(marketplace_name, label="plugin selector marketplace")
    if len(normalized_plugin_selector_list) != len(set(normalized_plugin_selector_list)):
        raise SkillBehaviorEvalError("duplicate --plugin selectors are forbidden")
    return normalized_plugin_selector_list


def _plugin_selector_by_name_map_get(plugin_selector_list: Sequence[str]) -> dict[str, str]:
    """Bind each plugin provider to exactly one declared source selector."""

    plugin_selector_by_name_map: dict[str, str] = {}
    for plugin_selector in _plugin_selector_tuple_normalize(plugin_selector_list):
        plugin_name = plugin_selector.split("@", 1)[0]
        if plugin_name in plugin_selector_by_name_map:
            raise SkillBehaviorEvalError(f"plugin provider has ambiguous source bindings: {plugin_name}")
        plugin_selector_by_name_map[plugin_name] = plugin_selector
    return plugin_selector_by_name_map


def _required_plugin_source_binding_validate(
    case_list: Sequence[SkillBehaviorCase],
    plugin_selector_by_name_map: dict[str, str],
    *,
    activated_skill_list: Sequence[str] = (),
) -> None:
    """Require every expected, forbidden or activated provider in the exact source set.

    Args:
        case_list: Ordered case values.
        plugin_selector_by_name_map: Exact validated source selector by provider.
        activated_skill_list: Ordered normalized activated skill values.
    """

    for plugin_name, plugin_selector in plugin_selector_by_name_map.items():
        normalized_plugin_selector_list = _plugin_selector_tuple_normalize([plugin_selector])
        if normalized_plugin_selector_list[0].split("@", 1)[0] != plugin_name:
            raise SkillBehaviorEvalError(f"plugin provider source binding identity is mismatched: {plugin_name}")
    required_plugin_name_set = {
        skill_name.split(":", 1)[0]
        for case in case_list
        for skill_name in (*case.expected_skill_list, *case.forbidden_skill_list)
        if ":" in skill_name
    }
    required_plugin_name_set.update(_activated_plugin_name_set_get(activated_skill_list))
    missing_plugin_name_list = sorted(required_plugin_name_set - set(plugin_selector_by_name_map))
    if missing_plugin_name_list:
        raise SkillBehaviorEvalError(
            "source binding omits plugins required by selected cases or actual activation: "
            + ", ".join(missing_plugin_name_list)
        )


def _activated_plugin_name_set_get(activated_skill_list: Sequence[str]) -> set[str]:
    """Derive each exact provider identity from normalized activated skills."""

    activated_plugin_name_set: set[str] = set()
    for activated_skill_name in activated_skill_list:
        if ":" not in activated_skill_name:
            continue
        if activated_skill_name.count(":") != 1:
            raise SkillBehaviorEvalError(
                f"activated skill has ambiguous provider identity: {activated_skill_name}"
            )
        plugin_name, skill_name = activated_skill_name.split(":", 1)
        _plugin_identity_validate(plugin_name, label="activated skill plugin name")
        _plugin_identity_validate(skill_name, label="activated skill name")
        activated_plugin_name_set.add(plugin_name)
    return activated_plugin_name_set


def _plugin_identity_validate(value: str, *, label: str) -> None:
    """Require one closed lowercase-hyphen plugin identity segment.

    Args:
        value: Candidate identity.
        label: Diagnostic identity owner.
    """

    if _PLUGIN_IDENTITY_PATTERN.fullmatch(value) is None:
        raise SkillBehaviorEvalError(f"{label} must be one closed single-segment identity")


def _generation_payload_validate(payload: dict[str, Any], *, case: SkillBehaviorCase) -> dict[str, Any]:
    """Validate one generation result beyond its JSON schema.

    Args:
        payload: Structured operation payload.
        case: Case.

    Returns:
        Validated generation response payload.
    """

    _exact_key_set_validate(
        payload,
        allowed_key_set={"activated_skill_list", "response"},
        context=f"{case.suite}:{case.id}.generation",
        required_key_set={"activated_skill_list", "response"},
    )
    activated_skill_list = _string_tuple_get(
        payload,
        context=f"{case.suite}:{case.id}.generation",
        field_name="activated_skill_list",
    )
    response = _non_empty_string_get(
        payload,
        context=f"{case.suite}:{case.id}.generation",
        field_name="response",
    )
    return {
        "activated_skill_list": list(activated_skill_list),
        "response": response,
    }


def _judge_result_tuple_get(
    payload: dict[str, Any],
    *,
    case: SkillBehaviorCase,
) -> tuple[SemanticInvariantResult, ...]:
    """Validate and normalize one independent judge result.

    Args:
        payload: Structured operation payload.
        case: Case.

    Returns:
        Values in deterministic immutable order.
    """

    _exact_key_set_validate(
        payload,
        allowed_key_set={"invariant_result_list"},
        context=f"{case.suite}:{case.id}.judge",
        required_key_set={"invariant_result_list"},
    )
    raw_result_list = payload["invariant_result_list"]
    if not isinstance(raw_result_list, list):
        raise SkillBehaviorEvalError(f"{case.suite}:{case.id}.judge.invariant_result_list: expected list")
    result_list: list[SemanticInvariantResult] = []
    for index, raw_result in enumerate(raw_result_list):
        result_context = f"{case.suite}:{case.id}.judge.invariant_result_list[{index}]"
        if not isinstance(raw_result, dict):
            raise SkillBehaviorEvalError(f"{result_context}: expected object")
        _exact_key_set_validate(
            raw_result,
            allowed_key_set={"id", "passed", "reason"},
            context=result_context,
            required_key_set={"id", "passed", "reason"},
        )
        passed = raw_result["passed"]
        if not isinstance(passed, bool):
            raise SkillBehaviorEvalError(f"{result_context}.passed: expected boolean")
        result_list.append(
            SemanticInvariantResult(
                id=_non_empty_string_get(raw_result, context=result_context, field_name="id"),
                passed=passed,
                reason=_non_empty_string_get(raw_result, context=result_context, field_name="reason"),
            )
        )
    expected_id_list = [invariant.id for invariant in case.semantic_invariant_list]
    actual_id_list = [result.id for result in result_list]
    if actual_id_list != expected_id_list:
        raise SkillBehaviorEvalError(
            f"{case.suite}:{case.id}.judge: invariant ids must be {expected_id_list!r}, got {actual_id_list!r}"
        )
    return tuple(result_list)


def _case_evaluate(
    case: SkillBehaviorCase,
    *,
    invocation_config: ModelInvocationConfig,
    plugin_selector_by_name_map: dict[str, str],
    model_call: ModelCall = _codex_payload_get,
) -> SkillBehaviorCaseResult:
    """Run generation and independent semantic judging for one case.

    Args:
        case: Case.
        invocation_config: Invocation config.
        plugin_selector_by_name_map: Exact validated source selector by provider.
        model_call: Model call.

    Returns:
        Resulting skill behavior case result.
    """

    generation_invocation = model_call(
        _generation_prompt_get(case),
        case.working_directory,
        _GENERATION_OUTPUT_SCHEMA,
        invocation_config,
    )
    generation_payload = _generation_payload_validate(
        generation_invocation.payload,
        case=case,
    )
    activated_skill_list = _activated_skill_tuple_normalize(
        generation_payload["activated_skill_list"],
        case=case,
    )
    _required_plugin_source_binding_validate(
        [case],
        plugin_selector_by_name_map,
        activated_skill_list=activated_skill_list,
    )
    judge_invocation = model_call(
        _judge_prompt_get(case=case, generation_payload=generation_payload),
        case.working_directory,
        _JUDGE_OUTPUT_SCHEMA,
        invocation_config,
    )
    judge_result_list = _judge_result_tuple_get(
        judge_invocation.payload,
        case=case,
    )
    activated_skill_set = set(activated_skill_list)
    missing_expected_skill_list = tuple(
        skill_name for skill_name in case.expected_skill_list if skill_name not in activated_skill_set
    )
    forbidden_activated_skill_list = tuple(
        skill_name for skill_name in case.forbidden_skill_list if skill_name in activated_skill_set
    )
    passed = (
        not missing_expected_skill_list
        and not forbidden_activated_skill_list
        and all(result.passed for result in judge_result_list)
    )
    return SkillBehaviorCaseResult(
        activated_skill_list=activated_skill_list,
        codex_usage_generation=generation_invocation.usage,
        codex_usage_judge=judge_invocation.usage,
        forbidden_activated_skill_list=forbidden_activated_skill_list,
        id=case.id,
        missing_expected_skill_list=missing_expected_skill_list,
        passed=passed,
        response=generation_payload["response"],
        semantic_invariant_result_list=judge_result_list,
        suite=case.suite,
    )


def _activated_skill_tuple_normalize(
    activated_skill_list: Sequence[str],
    *,
    case: SkillBehaviorCase,
) -> tuple[str, ...]:
    """Canonicalize an unqualified report only when the case makes its provider identity unambiguous.

    Args:
        activated_skill_list: Ordered activated skill values.
        case: Case.

    Returns:
        Values in deterministic immutable order.
    """

    canonical_skill_name_set = set(case.expected_skill_list) | set(case.forbidden_skill_list)
    canonical_skill_name_list_by_suffix_map: dict[str, list[str]] = {}
    for canonical_skill_name in canonical_skill_name_set:
        skill_suffix = canonical_skill_name.rsplit(":", maxsplit=1)[-1]
        canonical_skill_name_list_by_suffix_map.setdefault(skill_suffix, []).append(canonical_skill_name)

    normalized_skill_list: list[str] = []
    for activated_skill_name in activated_skill_list:
        candidate_list = canonical_skill_name_list_by_suffix_map.get(activated_skill_name, [])
        if len(candidate_list) > 1:
            raise SkillBehaviorEvalError(
                f"{case.suite}:{case.id}.generation activated skill has ambiguous provider identity: "
                f"{activated_skill_name}"
            )
        normalized_skill_name = candidate_list[0] if candidate_list else activated_skill_name
        if normalized_skill_name not in normalized_skill_list:
            normalized_skill_list.append(normalized_skill_name)
    return tuple(normalized_skill_list)


def _result_payload_get(
    *,
    invocation_config: ModelInvocationConfig,
    result_list: Sequence[SkillBehaviorCaseResult],
) -> dict[str, Any]:
    """Build the serializable run result.

    Args:
        invocation_config: Invocation config.
        result_list: Ordered result values.

    Returns:
        The serializable run result.
    """

    failed_case_id_list = [f"{result.suite}:{result.id}" for result in result_list if not result.passed]
    codex_usage = CodexUsage(
        cached_input_tokens=0,
        cache_write_input_tokens=0,
        input_tokens=0,
        output_tokens=0,
        reasoning_output_tokens=0,
    )
    for result in result_list:
        codex_usage = codex_usage.add(result.codex_usage_generation).add(result.codex_usage_judge)
    return {
        "case_result_list": [asdict(result) for result in result_list],
        "codex_usage": asdict(codex_usage),
        "failed_case_count": len(failed_case_id_list),
        "failed_case_id_list": failed_case_id_list,
        "model": invocation_config.model,
        "reasoning_effort": invocation_config.reasoning_effort,
        "run_timestamp": datetime.now(UTC).isoformat(),
        "schema_version": RESULT_SCHEMA_VERSION,
        "total_case_count": len(result_list),
    }


def _result_print(result: SkillBehaviorCaseResult) -> None:
    """Print one concise case result.

    Args:
        result: Result.
    """

    status = "PASS" if result.passed else "FAIL"
    print(f"{status} {result.suite}:{result.id}", flush=True)
    if result.missing_expected_skill_list:
        print(
            f"  missing_expected={','.join(result.missing_expected_skill_list)}",
            flush=True,
        )
    if result.forbidden_activated_skill_list:
        print(
            f"  forbidden_activated={','.join(result.forbidden_activated_skill_list)}",
            flush=True,
        )
    for invariant_result in result.semantic_invariant_result_list:
        if not invariant_result.passed:
            print(
                f"  invariant_failed={invariant_result.id}: {invariant_result.reason}",
                flush=True,
            )


def _output_destination_validate(output_path: Path) -> None:
    """Reject one already occupied or symlinked immutable result destination."""

    if output_path.exists() or output_path.is_symlink():
        raise SkillBehaviorEvalError(f"Output destination already exists: {output_path}")


def _result_output_publish(output_path: Path, payload: dict[str, Any]) -> None:
    """Publish one fully written result atomically at a previously absent path."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _output_destination_validate(output_path)
    serialized_result = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            delete=False,
            mode="w",
            encoding="utf-8",
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(serialized_result)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        temporary_path.chmod(0o644)
        try:
            os.link(temporary_path, output_path)
        except FileExistsError as error:
            raise SkillBehaviorEvalError(f"Output destination already exists: {output_path}") from error
        except OSError as error:
            raise SkillBehaviorEvalError(f"Cannot publish output destination: {output_path}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _case_list_evaluate(
    case_list: Sequence[SkillBehaviorCase],
    *,
    concurrency: int,
    invocation_config: ModelInvocationConfig,
    plugin_selector_by_name_map: dict[str, str],
) -> list[SkillBehaviorCaseResult]:
    """Evaluate cases concurrently while preserving corpus order in the result.

    Args:
        case_list: Ordered case values.
        concurrency: Concurrency.
        invocation_config: Invocation config.
        plugin_selector_by_name_map: Exact validated source selector by provider.

    Returns:
        Requested values in deterministic order.
    """

    result_by_index_map: dict[int, SkillBehaviorCaseResult] = {}
    with ThreadPoolExecutor(max_workers=min(concurrency, len(case_list))) as executor:
        future_by_index_map = {}
        for index, case in enumerate(case_list):
            print(f"RUN {case.suite}:{case.id}", flush=True)
            future = executor.submit(
                _case_evaluate,
                case,
                invocation_config=invocation_config,
                plugin_selector_by_name_map=plugin_selector_by_name_map,
            )
            future_by_index_map[future] = index
        for future in as_completed(future_by_index_map):
            result = future.result()
            result_by_index_map[future_by_index_map[future]] = result
            _result_print(result)
    return [result_by_index_map[index] for index in range(len(case_list))]


def main(argv_list: Sequence[str] | None = None) -> int:
    """Run selected skill behavior cases.

    Args:
        argv_list: Ordered argv values.

    Returns:
        Zero when all cases pass, 1 for semantic failures, or 2 for invalid evaluation input.
    """

    args = _argument_parser_get().parse_args(argv_list)
    try:
        if args.output is not None:
            _output_destination_validate(args.output)
        case_list = _selected_case_list_get(
            case_id_list=args.case_id_list,
            corpus_path_list=args.corpus_path_list,
        )
        if args.list:
            for case in case_list:
                print(f"{case.suite}:{case.id}")
            return 0
        standard_codex_home = Path(_standard_codex_process_environment_get()["HOME"]) / ".codex"
        plugin_selector_by_name_map = _preinstalled_plugin_source_binding_validate(
            case_list=case_list,
            marketplace_path_list=args.plugin_marketplace_path_list,
            plugin_selector_list=args.plugin_selector_list,
            standard_codex_home=standard_codex_home,
        )
        invocation_config = ModelInvocationConfig(
            codex_bin=args.codex_bin,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        result_list = _case_list_evaluate(
            case_list,
            concurrency=args.concurrency,
            invocation_config=invocation_config,
            plugin_selector_by_name_map=plugin_selector_by_name_map,
        )
        result_payload = _result_payload_get(
            invocation_config=invocation_config,
            result_list=result_list,
        )
        if args.output is not None:
            _result_output_publish(args.output, result_payload)
        print(
            f"total_case_count={result_payload['total_case_count']} "
            f"failed_case_count={result_payload['failed_case_count']}"
        )
        return 1 if result_payload["failed_case_count"] else 0
    except SkillBehaviorEvalError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
