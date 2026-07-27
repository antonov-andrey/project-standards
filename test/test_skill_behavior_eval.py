"""Behavior tests for the opt-in skill model-evaluation runner."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import time
from types import ModuleType
from typing import Any

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins/project-standards/skills/project-instruction-developer/scripts/skill_behavior_eval.py"
)


def _module_load() -> ModuleType:
    """Load the script as one isolated module."""

    spec = importlib.util.spec_from_file_location("skill_behavior_eval", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _corpus_write(path: Path, *, expected_skill_list: list[str] | None = None) -> None:
    """Write one minimal valid corpus."""

    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "suite": "provider",
                "case_list": [
                    {
                        "id": "case-a",
                        "working_directory": "..",
                        "prompt": "Review one Python function.",
                        "expected_skill_list": expected_skill_list or ["project-standards:python-developer"],
                        "forbidden_skill_list": ["agent-workflows:code-audit"],
                        "semantic_invariant_list": [
                            {
                                "id": "bounded",
                                "text": "The response remains a read-only review.",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_corpus_load_resolves_working_directory(tmp_path: Path) -> None:
    """A valid corpus should resolve its repository-relative working directory."""

    module = _module_load()
    corpus_root = tmp_path / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)

    case_list = module._corpus_case_list_load(corpus_path)

    assert len(case_list) == 1
    assert case_list[0].working_directory == tmp_path.resolve()
    assert case_list[0].semantic_invariant_list[0].id == "bounded"


def test_corpus_load_rejects_activation_overlap(tmp_path: Path) -> None:
    """One skill cannot be both expected and forbidden."""

    module = _module_load()
    corpus_root = tmp_path / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    payload["case_list"][0]["forbidden_skill_list"] = ["project-standards:python-developer"]
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(module.SkillBehaviorEvalError, match="expected and forbidden skills overlap"):
        module._corpus_case_list_load(corpus_path)


def test_case_evaluate_combines_activation_and_independent_judge(tmp_path: Path) -> None:
    """Case success should require expected activation and every semantic invariant."""

    module = _module_load()
    corpus_root = tmp_path / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    case = module._corpus_case_list_load(corpus_path)[0]
    call_list: list[dict[str, Any]] = []

    def _model_call(
        prompt: str,
        working_directory: Path,
        output_schema: dict[str, Any],
        invocation_config: Any,
    ) -> dict[str, Any]:
        """Return generation first and judge output second."""

        call_list.append(
            {
                "prompt": prompt,
                "working_directory": working_directory,
                "output_schema": output_schema,
                "invocation_config": invocation_config,
            }
        )
        if len(call_list) == 1:
            return {
                "activated_skill_list": ["project-standards:python-developer"],
                "response": "I inspected the function and found no issue; no files were changed.",
            }
        return {
            "invariant_result_list": [
                {
                    "id": "bounded",
                    "passed": True,
                    "reason": "The response reports a read-only inspection.",
                }
            ]
        }

    result = module._case_evaluate(
        case,
        invocation_config=module.ModelInvocationConfig(
            codex_bin="codex",
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            timeout_seconds=60,
        ),
        model_call=_model_call,
    )

    assert result.passed is True
    assert result.missing_expected_skill_list == ()
    assert len(call_list) == 2
    assert "Do not use keyword" in call_list[1]["prompt"]


def test_case_evaluate_reports_missing_and_forbidden_activations(tmp_path: Path) -> None:
    """Activation failures should be independent from a passing semantic judge."""

    module = _module_load()
    corpus_root = tmp_path / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    case = module._corpus_case_list_load(corpus_path)[0]
    payload_list = iter(
        [
            {
                "activated_skill_list": ["agent-workflows:code-audit"],
                "response": "Read-only audit response.",
            },
            {
                "invariant_result_list": [
                    {
                        "id": "bounded",
                        "passed": True,
                        "reason": "No mutation is proposed.",
                    }
                ]
            },
        ]
    )

    result = module._case_evaluate(
        case,
        invocation_config=module.ModelInvocationConfig(
            codex_bin="codex",
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            timeout_seconds=60,
        ),
        model_call=lambda *_args: next(payload_list),
    )

    assert result.passed is False
    assert result.missing_expected_skill_list == ("project-standards:python-developer",)
    assert result.forbidden_activated_skill_list == ("agent-workflows:code-audit",)


def test_activation_normalization_requires_one_unambiguous_provider_identity(tmp_path: Path) -> None:
    """A short self-report should canonicalize only against one exact case identity."""

    module = _module_load()
    corpus_root = tmp_path / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    case = module._corpus_case_list_load(corpus_path)[0]

    assert module._activated_skill_tuple_normalize(["python-developer"], case=case) == (
        "project-standards:python-developer",
    )

    ambiguous_case = module.SkillBehaviorCase(
        corpus_path=case.corpus_path,
        expected_skill_list=("provider-a:shared",),
        forbidden_skill_list=("provider-b:shared",),
        id=case.id,
        prompt=case.prompt,
        semantic_invariant_list=case.semantic_invariant_list,
        suite=case.suite,
        working_directory=case.working_directory,
    )
    assert module._activated_skill_tuple_normalize(["shared"], case=ambiguous_case) == ("shared",)


def test_case_list_evaluate_preserves_corpus_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Concurrent completion order must not change the serialized corpus order."""

    module = _module_load()
    corpus_root = tmp_path / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    first_case = module._corpus_case_list_load(corpus_path)[0]
    second_case = module.SkillBehaviorCase(
        corpus_path=first_case.corpus_path,
        expected_skill_list=first_case.expected_skill_list,
        forbidden_skill_list=first_case.forbidden_skill_list,
        id="case-b",
        prompt=first_case.prompt,
        semantic_invariant_list=first_case.semantic_invariant_list,
        suite=first_case.suite,
        working_directory=first_case.working_directory,
    )

    def _case_evaluate(case: Any, *, invocation_config: Any) -> Any:
        """Return the second case first."""

        if case.id == "case-a":
            time.sleep(0.02)
        return module.SkillBehaviorCaseResult(
            activated_skill_list=(),
            forbidden_activated_skill_list=(),
            id=case.id,
            missing_expected_skill_list=(),
            passed=True,
            response="response",
            semantic_invariant_result_list=(),
            suite=case.suite,
        )

    monkeypatch.setattr(module, "_case_evaluate", _case_evaluate)
    result_list = module._case_list_evaluate(
        [first_case, second_case],
        concurrency=2,
        invocation_config=module.ModelInvocationConfig(
            codex_bin="codex",
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            timeout_seconds=60,
        ),
    )

    assert [result.id for result in result_list] == ["case-a", "case-b"]
