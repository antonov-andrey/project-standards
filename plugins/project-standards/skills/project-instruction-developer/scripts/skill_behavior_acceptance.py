#!/usr/bin/env python3
"""Derive the next failed-only behavior-evaluation acceptance subset."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TARGET_MODEL = "gpt-5.6-sol"
TARGET_REASONING_EFFORT = "max"
LEGACY_RESULT_SCHEMA_VERSION = 1
RESULT_SCHEMA_VERSION = 2
STATE_SCHEMA_VERSION = 1


class SkillBehaviorAcceptanceError(RuntimeError):
    """Report one invalid or non-convergent evaluation result sequence."""


def _required_text(payload: dict[str, Any], field_name: str, *, context: str) -> str:
    """Return one required non-empty text field.

    Args:
        payload: Result object containing the field.
        field_name: Exact field name.
        context: Diagnostic result location.

    Returns:
        Validated text.
    """

    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise SkillBehaviorAcceptanceError(f"{context}.{field_name} must be non-empty text")
    return value


_CODEX_USAGE_FIELD_TUPLE = (
    "cached_input_tokens",
    "cache_write_input_tokens",
    "input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def _codex_usage_validate(payload: object, *, context: str) -> dict[str, int]:
    """Validate the exact aggregate counter shape from the current runner.

    Args:
        payload: Candidate aggregate usage payload.
        context: Diagnostic result location.
    """

    expected_key_set = set(_CODEX_USAGE_FIELD_TUPLE)
    if not isinstance(payload, dict) or set(payload) != expected_key_set:
        raise SkillBehaviorAcceptanceError(f"{context} has another shape")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in payload.values()):
        raise SkillBehaviorAcceptanceError(f"{context} counters must be non-negative integers")
    if payload["cached_input_tokens"] > payload["input_tokens"]:
        raise SkillBehaviorAcceptanceError(f"{context}.cached_input_tokens exceeds input_tokens")
    if payload["cache_write_input_tokens"] > payload["input_tokens"]:
        raise SkillBehaviorAcceptanceError(f"{context}.cache_write_input_tokens exceeds input_tokens")
    if payload["reasoning_output_tokens"] > payload["output_tokens"]:
        raise SkillBehaviorAcceptanceError(f"{context}.reasoning_output_tokens exceeds output_tokens")
    return payload


def _text_list_get(payload: dict[str, Any], field_name: str, *, context: str) -> tuple[str, ...]:
    """Return one exact duplicate-free list of non-empty strings."""

    value = payload.get(field_name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise SkillBehaviorAcceptanceError(f"{context}.{field_name} must be a list of non-empty text")
    if len(value) != len(set(value)):
        raise SkillBehaviorAcceptanceError(f"{context}.{field_name} must not repeat values")
    return tuple(value)


def _run_timestamp_validate(payload: dict[str, Any], *, context: str) -> None:
    """Require one parseable UTC result timestamp."""

    value = _required_text(payload, "run_timestamp", context=context)
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise SkillBehaviorAcceptanceError(f"{context}.run_timestamp must be an ISO 8601 timestamp") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
        raise SkillBehaviorAcceptanceError(f"{context}.run_timestamp must use UTC")


def _case_result_tuple_get(payload: object, *, context: str) -> tuple[tuple[str, bool], ...]:
    """Return ordered suite-qualified case outcomes from one runner result.

    Args:
        payload: Candidate runner result.
        context: Diagnostic result location.

    Returns:
        Ordered case ID and pass-state pairs.
    """

    if not isinstance(payload, dict):
        raise SkillBehaviorAcceptanceError(f"{context} must be one result object")
    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version not in {
        LEGACY_RESULT_SCHEMA_VERSION,
        RESULT_SCHEMA_VERSION,
    }:
        raise SkillBehaviorAcceptanceError(
            f"{context}.schema_version must equal {LEGACY_RESULT_SCHEMA_VERSION} or {RESULT_SCHEMA_VERSION}"
        )
    expected_key_set = {
        "case_result_list",
        "failed_case_count",
        "model",
        "reasoning_effort",
        "run_timestamp",
        "schema_version",
        "total_case_count",
    }
    if schema_version == RESULT_SCHEMA_VERSION:
        expected_key_set |= {"codex_usage", "failed_case_id_list"}
    if set(payload) != expected_key_set:
        raise SkillBehaviorAcceptanceError(f"{context} has another schema-v{schema_version} shape")
    if payload.get("model") != TARGET_MODEL or payload.get("reasoning_effort") != TARGET_REASONING_EFFORT:
        raise SkillBehaviorAcceptanceError(
            f"{context} must use {TARGET_MODEL} with reasoning_effort={TARGET_REASONING_EFFORT}"
        )
    raw_result_list = payload.get("case_result_list")
    if not isinstance(raw_result_list, list) or not raw_result_list:
        raise SkillBehaviorAcceptanceError(f"{context}.case_result_list must be a non-empty list")
    _run_timestamp_validate(payload, context=context)
    case_result_list: list[tuple[str, bool]] = []
    aggregate_usage = {field_name: 0 for field_name in _CODEX_USAGE_FIELD_TUPLE}
    for index, raw_result in enumerate(raw_result_list):
        result_context = f"{context}.case_result_list[{index}]"
        if not isinstance(raw_result, dict):
            raise SkillBehaviorAcceptanceError(f"{result_context} must be one case result object")
        expected_case_key_set = {
            "activated_skill_list",
            "forbidden_activated_skill_list",
            "id",
            "missing_expected_skill_list",
            "passed",
            "response",
            "semantic_invariant_result_list",
            "suite",
        }
        if schema_version == RESULT_SCHEMA_VERSION:
            expected_case_key_set |= {"codex_usage_generation", "codex_usage_judge"}
        if set(raw_result) != expected_case_key_set:
            raise SkillBehaviorAcceptanceError(f"{result_context} has another schema-v{schema_version} shape")
        suite = _required_text(raw_result, "suite", context=result_context)
        case_id = _required_text(raw_result, "id", context=result_context)
        _required_text(raw_result, "response", context=result_context)
        activated_skill_tuple = _text_list_get(raw_result, "activated_skill_list", context=result_context)
        missing_skill_tuple = _text_list_get(raw_result, "missing_expected_skill_list", context=result_context)
        forbidden_skill_tuple = _text_list_get(
            raw_result,
            "forbidden_activated_skill_list",
            context=result_context,
        )
        if not set(forbidden_skill_tuple).issubset(activated_skill_tuple):
            raise SkillBehaviorAcceptanceError(
                f"{result_context}.forbidden_activated_skill_list is not a subset of activated_skill_list"
            )
        if set(missing_skill_tuple) & set(activated_skill_tuple):
            raise SkillBehaviorAcceptanceError(
                f"{result_context}.missing_expected_skill_list intersects activated_skill_list"
            )
        invariant_result_list = raw_result.get("semantic_invariant_result_list")
        if not isinstance(invariant_result_list, list) or not invariant_result_list:
            raise SkillBehaviorAcceptanceError(
                f"{result_context}.semantic_invariant_result_list must be a non-empty list"
            )
        invariant_passed_list: list[bool] = []
        invariant_id_list: list[str] = []
        for invariant_index, invariant_result in enumerate(invariant_result_list):
            invariant_context = f"{result_context}.semantic_invariant_result_list[{invariant_index}]"
            if not isinstance(invariant_result, dict) or set(invariant_result) != {"id", "passed", "reason"}:
                raise SkillBehaviorAcceptanceError(f"{invariant_context} has another shape")
            invariant_id_list.append(_required_text(invariant_result, "id", context=invariant_context))
            _required_text(invariant_result, "reason", context=invariant_context)
            invariant_passed = invariant_result.get("passed")
            if not isinstance(invariant_passed, bool):
                raise SkillBehaviorAcceptanceError(f"{invariant_context}.passed must be boolean")
            invariant_passed_list.append(invariant_passed)
        if len(invariant_id_list) != len(set(invariant_id_list)):
            raise SkillBehaviorAcceptanceError(
                f"{result_context}.semantic_invariant_result_list repeats one invariant ID"
            )
        passed = raw_result.get("passed")
        if not isinstance(passed, bool):
            raise SkillBehaviorAcceptanceError(f"{result_context}.passed must be boolean")
        recomputed_passed = not missing_skill_tuple and not forbidden_skill_tuple and all(invariant_passed_list)
        if passed != recomputed_passed:
            raise SkillBehaviorAcceptanceError(f"{result_context}.passed differs from its recomputed verdict")
        if schema_version == RESULT_SCHEMA_VERSION:
            for usage_field_name in ("codex_usage_generation", "codex_usage_judge"):
                usage = _codex_usage_validate(
                    raw_result[usage_field_name],
                    context=f"{result_context}.{usage_field_name}",
                )
                for counter_name in _CODEX_USAGE_FIELD_TUPLE:
                    aggregate_usage[counter_name] += usage[counter_name]
        case_result_list.append((f"{suite}:{case_id}", passed))
    case_id_list = [case_id for case_id, _passed in case_result_list]
    if len(case_id_list) != len(set(case_id_list)):
        raise SkillBehaviorAcceptanceError(f"{context} repeats one suite-qualified case ID")
    failed_case_id_list = [case_id for case_id, passed in case_result_list if not passed]
    total_case_count = payload.get("total_case_count")
    if type(total_case_count) is not int or total_case_count != len(case_result_list):
        raise SkillBehaviorAcceptanceError(f"{context}.total_case_count differs from its case outcomes")
    failed_case_count = payload.get("failed_case_count")
    if type(failed_case_count) is not int or failed_case_count != len(failed_case_id_list):
        raise SkillBehaviorAcceptanceError(f"{context}.failed_case_count differs from its case outcomes")
    if schema_version == RESULT_SCHEMA_VERSION and payload.get("failed_case_id_list") != failed_case_id_list:
        raise SkillBehaviorAcceptanceError(f"{context}.failed_case_id_list differs from its case outcomes")
    if schema_version == RESULT_SCHEMA_VERSION:
        declared_usage = _codex_usage_validate(payload["codex_usage"], context=f"{context}.codex_usage")
        if declared_usage != aggregate_usage:
            raise SkillBehaviorAcceptanceError(f"{context}.codex_usage differs from recomputed case usage")
    return tuple(case_result_list)


@dataclass(frozen=True, slots=True)
class SkillBehaviorAcceptanceState:
    """Track one monotonic failed-subset acceptance cycle."""

    selected_case_id_tuple: tuple[str, ...]
    pending_case_id_tuple: tuple[str, ...]
    passed_case_id_tuple: tuple[str, ...]
    completed_iteration_count: int

    @classmethod
    def start(cls, selected_case_id_list: Sequence[str]) -> SkillBehaviorAcceptanceState:
        """Start one cycle before accepting its complete first result.

        Args:
            selected_case_id_list: Complete ordered initial selection.

        Returns:
            Initial pending state.
        """

        selected_case_id_tuple = tuple(selected_case_id_list)
        if not selected_case_id_tuple or len(selected_case_id_tuple) != len(set(selected_case_id_tuple)):
            raise SkillBehaviorAcceptanceError("Acceptance selection must contain unique case IDs")
        return cls(
            selected_case_id_tuple=selected_case_id_tuple,
            pending_case_id_tuple=selected_case_id_tuple,
            passed_case_id_tuple=(),
            completed_iteration_count=0,
        )

    def result_accept(self, payload: object, *, context: str) -> SkillBehaviorAcceptanceState:
        """Accept exactly the current pending set and remove every passed case.

        Args:
            payload: Current runner result.
            context: Diagnostic result location.

        Returns:
            Next monotonic acceptance state.
        """

        if not self.pending_case_id_tuple:
            raise SkillBehaviorAcceptanceError("A completed acceptance cycle cannot accept another result")
        case_result_tuple = _case_result_tuple_get(payload, context=context)
        return self._case_result_tuple_accept(case_result_tuple, context=context)

    def _case_result_tuple_accept(
        self,
        case_result_tuple: tuple[tuple[str, bool], ...],
        *,
        context: str,
    ) -> SkillBehaviorAcceptanceState:
        """Apply one already validated exact result tuple."""

        result_case_id_tuple = tuple(case_id for case_id, _passed in case_result_tuple)
        if result_case_id_tuple != self.pending_case_id_tuple:
            raise SkillBehaviorAcceptanceError(f"{context} must evaluate exactly the current failed case set")
        failed_case_id_set = {case_id for case_id, passed in case_result_tuple if not passed}
        passed_case_id_set = set(self.passed_case_id_tuple) | {
            case_id for case_id, passed in case_result_tuple if passed
        }
        return SkillBehaviorAcceptanceState(
            selected_case_id_tuple=self.selected_case_id_tuple,
            pending_case_id_tuple=tuple(
                case_id for case_id in self.selected_case_id_tuple if case_id in failed_case_id_set
            ),
            passed_case_id_tuple=tuple(
                case_id for case_id in self.selected_case_id_tuple if case_id in passed_case_id_set
            ),
            completed_iteration_count=self.completed_iteration_count + 1,
        )

    def payload(self) -> dict[str, Any]:
        """Return the exact next-step state for the acceptance operator.

        Returns:
            JSON-ready current state and direct next-case arguments.
        """

        next_case_argument_list = [
            argument for case_id in self.pending_case_id_tuple for argument in ("--case", case_id)
        ]
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "complete": not self.pending_case_id_tuple,
            "completed_iteration_count": self.completed_iteration_count,
            "failed_case_id_list": list(self.pending_case_id_tuple),
            "next_case_argument_list": next_case_argument_list,
            "passed_case_id_list": list(self.passed_case_id_tuple),
            "selected_case_id_list": list(self.selected_case_id_tuple),
        }


def acceptance_state_get(
    result_payload_list: Sequence[object],
) -> SkillBehaviorAcceptanceState:
    """Replay one immutable result sequence into its current convergence state.

    Args:
        result_payload_list: Initial result followed by targeted results.

    Returns:
        Current monotonic acceptance state.
    """

    if not result_payload_list:
        raise SkillBehaviorAcceptanceError("At least one evaluation result is required")
    first_case_result_tuple = _case_result_tuple_get(result_payload_list[0], context="result[0]")
    state = SkillBehaviorAcceptanceState.start([case_id for case_id, _passed in first_case_result_tuple])
    state = state._case_result_tuple_accept(first_case_result_tuple, context="result[0]")
    for index, result_payload in enumerate(result_payload_list[1:], start=1):
        state = state.result_accept(result_payload, context=f"result[{index}]")
    return state


def _result_load(path: Path) -> object:
    """Load one UTF-8 JSON result without accepting malformed data.

    Args:
        path: Immutable runner result path.

    Returns:
        Decoded JSON value.
    """

    try:
        def object_pairs_get(pair_list: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pair_list:
                if key in result:
                    raise SkillBehaviorAcceptanceError(f"Acceptance result repeats JSON key {key!r}")
                result[key] = value
            return result

        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=object_pairs_get)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SkillBehaviorAcceptanceError(f"Cannot load acceptance result {path}") from error


def _argument_parser_get() -> argparse.ArgumentParser:
    """Build the deterministic result-replay CLI.

    Returns:
        Configured argument parser.
    """

    parser = argparse.ArgumentParser(
        description="Derive the next failed-only skill behavior evaluation subset.",
    )
    parser.add_argument(
        "--result",
        action="append",
        dest="result_path_list",
        required=True,
        type=Path,
        help="Ordered runner result JSON; repeat from the initial pass through the latest targeted pass.",
    )
    return parser


def main(argv_list: Sequence[str] | None = None) -> int:
    """Print the current cycle state; return 0 only when it converged.

    Args:
        argv_list: Optional exact command arguments.

    Returns:
        Zero for convergence, 1 for remaining failures, or 2 for invalid results.
    """

    args = _argument_parser_get().parse_args(argv_list)
    try:
        state = acceptance_state_get([_result_load(path) for path in args.result_path_list])
    except SkillBehaviorAcceptanceError as error:
        print(f"ERROR: {error}")
        return 2
    print(json.dumps(state.payload(), ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0 if not state.pending_case_id_tuple else 1


if __name__ == "__main__":
    raise SystemExit(main())
