#!/usr/bin/env python3
"""Run opt-in model-based activation and output evaluations for skills."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from concurrent.futures import as_completed, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_TIMEOUT_SECONDS = 600
SCHEMA_VERSION = 1

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


@dataclass(frozen=True)
class SemanticInvariant:
    """Define one semantic property required from the generated response."""

    id: str
    text: str


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class ModelInvocationConfig:
    """Store one immutable Codex model invocation configuration."""

    codex_bin: str
    model: str
    reasoning_effort: str
    timeout_seconds: int


@dataclass(frozen=True)
class SemanticInvariantResult:
    """Store one judge verdict."""

    id: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class SkillBehaviorCaseResult:
    """Store complete activation and semantic results for one case."""

    activated_skill_list: tuple[str, ...]
    forbidden_activated_skill_list: tuple[str, ...]
    id: str
    missing_expected_skill_list: tuple[str, ...]
    passed: bool
    response: str
    semantic_invariant_result_list: tuple[SemanticInvariantResult, ...]
    suite: str


ModelCall = Callable[[str, Path, dict[str, Any], ModelInvocationConfig], dict[str, Any]]


def _positive_int_get(value: str) -> int:
    """Parse one positive integer CLI value."""

    parsed_value = int(value)
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed_value


def _argument_parser_get() -> argparse.ArgumentParser:
    """Build the command-line parser."""

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
    parser.add_argument(
        "--timeout-seconds",
        default=DEFAULT_TIMEOUT_SECONDS,
        type=_positive_int_get,
        help=f"Timeout for each Codex invocation; default: {DEFAULT_TIMEOUT_SECONDS}.",
    )
    return parser


def _exact_key_set_validate(
    payload: dict[str, Any],
    *,
    allowed_key_set: set[str],
    context: str,
    required_key_set: set[str],
) -> None:
    """Validate exact required and allowed object keys."""

    missing_key_set = required_key_set - set(payload)
    unknown_key_set = set(payload) - allowed_key_set
    if missing_key_set:
        raise SkillBehaviorEvalError(f"{context}: missing fields: {', '.join(sorted(missing_key_set))}")
    if unknown_key_set:
        raise SkillBehaviorEvalError(f"{context}: unknown fields: {', '.join(sorted(unknown_key_set))}")


def _non_empty_string_get(payload: dict[str, Any], *, context: str, field_name: str) -> str:
    """Return one validated non-empty string field."""

    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise SkillBehaviorEvalError(f"{context}.{field_name}: expected non-empty string")
    return value.strip()


def _string_tuple_get(payload: dict[str, Any], *, context: str, field_name: str) -> tuple[str, ...]:
    """Return one validated unique string-list field."""

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
    """Return validated semantic invariants."""

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


def _corpus_case_list_load(corpus_path: Path) -> list[SkillBehaviorCase]:
    """Load and validate all cases from one corpus."""

    resolved_corpus_path = corpus_path.expanduser().resolve()
    try:
        payload = json.loads(resolved_corpus_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillBehaviorEvalError(f"{resolved_corpus_path}: cannot load corpus: {exc}") from exc
    if not isinstance(payload, dict):
        raise SkillBehaviorEvalError(f"{resolved_corpus_path}: corpus root must be an object")
    _exact_key_set_validate(
        payload,
        allowed_key_set={"case_list", "schema_version", "suite"},
        context=str(resolved_corpus_path),
        required_key_set={"case_list", "schema_version", "suite"},
    )
    if payload["schema_version"] != SCHEMA_VERSION:
        raise SkillBehaviorEvalError(
            f"{resolved_corpus_path}: schema_version must equal {SCHEMA_VERSION}, got {payload['schema_version']!r}"
        )
    suite = _non_empty_string_get(payload, context=str(resolved_corpus_path), field_name="suite")
    raw_case_list = payload["case_list"]
    if not isinstance(raw_case_list, list) or not raw_case_list:
        raise SkillBehaviorEvalError(f"{resolved_corpus_path}.case_list: expected non-empty object list")

    case_list: list[SkillBehaviorCase] = []
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
            },
            context=case_context,
            required_key_set={
                "expected_skill_list",
                "forbidden_skill_list",
                "id",
                "prompt",
                "semantic_invariant_list",
                "working_directory",
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
        working_directory_value = _non_empty_string_get(
            raw_case,
            context=case_context,
            field_name="working_directory",
        )
        working_directory = (resolved_corpus_path.parent / working_directory_value).resolve()
        if not working_directory.is_dir():
            raise SkillBehaviorEvalError(f"{case_context}.working_directory: not a directory: {working_directory}")
        case_list.append(
            SkillBehaviorCase(
                corpus_path=resolved_corpus_path,
                expected_skill_list=expected_skill_list,
                forbidden_skill_list=forbidden_skill_list,
                id=_non_empty_string_get(raw_case, context=case_context, field_name="id"),
                prompt=_non_empty_string_get(raw_case, context=case_context, field_name="prompt"),
                semantic_invariant_list=_semantic_invariant_tuple_get(raw_case, context=case_context),
                suite=suite,
                working_directory=working_directory,
            )
        )
    case_id_list = [case.id for case in case_list]
    if len(case_id_list) != len(set(case_id_list)):
        raise SkillBehaviorEvalError(f"{resolved_corpus_path}: duplicate case ids are forbidden")
    return case_list


def _selected_case_list_get(
    *,
    case_id_list: Sequence[str],
    corpus_path_list: Sequence[Path],
) -> list[SkillBehaviorCase]:
    """Load corpora and apply exact case selection."""

    case_list = [case for corpus_path in corpus_path_list for case in _corpus_case_list_load(corpus_path)]
    qualified_id_list = [f"{case.suite}:{case.id}" for case in case_list]
    if len(qualified_id_list) != len(set(qualified_id_list)):
        raise SkillBehaviorEvalError("duplicate suite-qualified case ids are forbidden")
    if not case_id_list:
        return case_list
    requested_case_id_set = set(case_id_list)
    selected_case_list = [
        case
        for case in case_list
        if case.id in requested_case_id_set or f"{case.suite}:{case.id}" in requested_case_id_set
    ]
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
    """Build the isolated generation prompt for one case."""

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
    """Build an independent semantic judge prompt for one generated response."""

    invariant_payload = [asdict(invariant) for invariant in case.semantic_invariant_list]
    return f"""Act as an independent semantic evaluator. Do not inspect files and do not improve the answer.

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


def _codex_payload_get(
    prompt: str,
    working_directory: Path,
    output_schema: dict[str, Any],
    invocation_config: ModelInvocationConfig,
) -> dict[str, Any]:
    """Invoke Codex once and return its structured final payload."""

    with tempfile.TemporaryDirectory(prefix="skill-behavior-eval-") as temporary_directory_value:
        temporary_directory = Path(temporary_directory_value)
        output_path = temporary_directory / "output.json"
        schema_path = temporary_directory / "schema.json"
        schema_path.write_text(json.dumps(output_schema, ensure_ascii=False), encoding="utf-8")
        command = [
            invocation_config.codex_bin,
            "exec",
            "--ephemeral",
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
        try:
            completed_process = subprocess.run(
                command,
                check=False,
                capture_output=True,
                input=prompt,
                text=True,
                timeout=invocation_config.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
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
    return payload


def _generation_payload_validate(payload: dict[str, Any], *, case: SkillBehaviorCase) -> dict[str, Any]:
    """Validate one generation result beyond its JSON schema."""

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
    """Validate and normalize one independent judge result."""

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
    model_call: ModelCall = _codex_payload_get,
) -> SkillBehaviorCaseResult:
    """Run generation and independent semantic judging for one case."""

    generation_payload = _generation_payload_validate(
        model_call(
            _generation_prompt_get(case),
            case.working_directory,
            _GENERATION_OUTPUT_SCHEMA,
            invocation_config,
        ),
        case=case,
    )
    judge_result_list = _judge_result_tuple_get(
        model_call(
            _judge_prompt_get(case=case, generation_payload=generation_payload),
            case.working_directory,
            _JUDGE_OUTPUT_SCHEMA,
            invocation_config,
        ),
        case=case,
    )
    activated_skill_list = _activated_skill_tuple_normalize(
        generation_payload["activated_skill_list"],
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
    """Canonicalize an unqualified report only when the case makes its provider identity unambiguous."""

    canonical_skill_name_set = set(case.expected_skill_list) | set(case.forbidden_skill_list)
    canonical_skill_name_list_by_suffix_map: dict[str, list[str]] = {}
    for canonical_skill_name in canonical_skill_name_set:
        skill_suffix = canonical_skill_name.rsplit(":", maxsplit=1)[-1]
        canonical_skill_name_list_by_suffix_map.setdefault(skill_suffix, []).append(canonical_skill_name)

    normalized_skill_list: list[str] = []
    for activated_skill_name in activated_skill_list:
        candidate_list = canonical_skill_name_list_by_suffix_map.get(activated_skill_name, [])
        normalized_skill_name = candidate_list[0] if len(candidate_list) == 1 else activated_skill_name
        if normalized_skill_name not in normalized_skill_list:
            normalized_skill_list.append(normalized_skill_name)
    return tuple(normalized_skill_list)


def _result_payload_get(
    *,
    invocation_config: ModelInvocationConfig,
    result_list: Sequence[SkillBehaviorCaseResult],
) -> dict[str, Any]:
    """Build the serializable run result."""

    return {
        "case_result_list": [asdict(result) for result in result_list],
        "failed_case_count": sum(not result.passed for result in result_list),
        "model": invocation_config.model,
        "reasoning_effort": invocation_config.reasoning_effort,
        "run_timestamp": datetime.now(UTC).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "total_case_count": len(result_list),
    }


def _result_print(result: SkillBehaviorCaseResult) -> None:
    """Print one concise case result."""

    status = "PASS" if result.passed else "FAIL"
    print(f"{status} {result.suite}:{result.id}", flush=True)
    if result.missing_expected_skill_list:
        print(f"  missing_expected={','.join(result.missing_expected_skill_list)}", flush=True)
    if result.forbidden_activated_skill_list:
        print(f"  forbidden_activated={','.join(result.forbidden_activated_skill_list)}", flush=True)
    for invariant_result in result.semantic_invariant_result_list:
        if not invariant_result.passed:
            print(f"  invariant_failed={invariant_result.id}: {invariant_result.reason}", flush=True)


def _case_list_evaluate(
    case_list: Sequence[SkillBehaviorCase],
    *,
    concurrency: int,
    invocation_config: ModelInvocationConfig,
) -> list[SkillBehaviorCaseResult]:
    """Evaluate cases concurrently while preserving corpus order in the result."""

    result_by_index_map: dict[int, SkillBehaviorCaseResult] = {}
    with ThreadPoolExecutor(max_workers=min(concurrency, len(case_list))) as executor:
        future_by_index_map = {}
        for index, case in enumerate(case_list):
            print(f"RUN {case.suite}:{case.id}", flush=True)
            future = executor.submit(
                _case_evaluate,
                case,
                invocation_config=invocation_config,
            )
            future_by_index_map[future] = index
        for future in as_completed(future_by_index_map):
            result = future.result()
            result_by_index_map[future_by_index_map[future]] = result
            _result_print(result)
    return [result_by_index_map[index] for index in range(len(case_list))]


def main(argv_list: Sequence[str] | None = None) -> int:
    """Run selected skill behavior cases."""

    args = _argument_parser_get().parse_args(argv_list)
    try:
        case_list = _selected_case_list_get(
            case_id_list=args.case_id_list,
            corpus_path_list=args.corpus_path_list,
        )
        if args.list:
            for case in case_list:
                print(f"{case.suite}:{case.id}")
            return 0
        invocation_config = ModelInvocationConfig(
            codex_bin=args.codex_bin,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            timeout_seconds=args.timeout_seconds,
        )
        result_list = _case_list_evaluate(
            case_list,
            concurrency=args.concurrency,
            invocation_config=invocation_config,
        )
        result_payload = _result_payload_get(
            invocation_config=invocation_config,
            result_list=result_list,
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
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
