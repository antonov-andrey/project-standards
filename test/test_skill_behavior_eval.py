"""Behavior tests for the opt-in skill model-evaluation runner."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
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


def _git_run(repository: Path, argument_list: list[str]) -> str:
    """Run one checked Git command in a test repository."""

    result = subprocess.run(
        ["git", "-C", str(repository), *argument_list],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _repository_create(repository: Path) -> None:
    """Create one minimal main-branch test repository."""

    repository.mkdir()
    _git_run(repository, ["init", "-b", "main"])
    _git_run(repository, ["config", "user.email", "test@example.com"])
    _git_run(repository, ["config", "user.name", "Behavior Eval Test"])
    (repository / "README.md").write_text("baseline\n", encoding="utf-8")
    _git_run(repository, ["add", "README.md"])
    _git_run(repository, ["commit", "-m", "Initial test state"])


def _separate_git_directory_repository_create(repository: Path, git_directory: Path) -> None:
    """Create one main worktree whose Git administration lives elsewhere."""

    _git_run(
        repository.parent,
        [
            "init",
            "-b",
            "main",
            f"--separate-git-dir={git_directory}",
            str(repository),
        ],
    )
    _git_run(repository, ["config", "user.email", "test@example.com"])
    _git_run(repository, ["config", "user.name", "Behavior Eval Test"])
    (repository / "README.md").write_text("baseline\n", encoding="utf-8")
    _git_run(repository, ["add", "README.md"])
    _git_run(repository, ["commit", "-m", "Initial test state"])


def test_corpus_load_resolves_working_directory(tmp_path: Path) -> None:
    """A valid corpus should resolve its repository-relative working directory."""

    module = _module_load()
    repository = tmp_path / "repository"
    _repository_create(repository)
    corpus_root = repository / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)

    case_list = module._corpus_case_list_load(corpus_path)

    assert len(case_list) == 1
    assert case_list[0].working_directory == repository.resolve()
    assert case_list[0].semantic_invariant_list[0].id == "bounded"


def test_corpus_load_rejects_boolean_schema_version(tmp_path: Path) -> None:
    """A boolean must not alias the integer version in the closed corpus schema."""

    module = _module_load()
    corpus_path = tmp_path / "corpus-v1.json"
    _corpus_write(corpus_path)
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    payload["schema_version"] = True
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(module.SkillBehaviorEvalError, match="schema_version must equal 1"):
        module._corpus_case_list_load(corpus_path)


def test_git_discovery_ignores_inherited_repository_redirection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Repository discovery must not honor caller-controlled Git redirect state."""

    module = _module_load()
    intended_repository = tmp_path / "intended"
    sentinel_repository = tmp_path / "sentinel"
    _repository_create(intended_repository)
    _repository_create(sentinel_repository)
    (intended_repository / "README.md").write_text("intended dirty state\n", encoding="utf-8")
    injected_config_path = tmp_path / "injected.gitconfig"
    injected_config_path.write_text(
        f"[core]\n\tworktree = {sentinel_repository}\n",
        encoding="utf-8",
    )
    for variable_name, value in {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_GLOBAL": str(injected_config_path),
        "GIT_CONFIG_KEY_0": "core.worktree",
        "GIT_CONFIG_PARAMETERS": "'core.worktree'='{}'".format(sentinel_repository),
        "GIT_CONFIG_VALUE_0": str(sentinel_repository),
        "GIT_DIR": str(sentinel_repository / ".git"),
        "GIT_INDEX_FILE": str(sentinel_repository / ".git" / "index"),
        "GIT_WORK_TREE": str(sentinel_repository),
    }.items():
        monkeypatch.setenv(variable_name, value)

    discovered_root = module._git_repository_root_get(
        intended_repository,
        context="sentinel regression",
    )
    status_text = module._git_output_get(
        intended_repository,
        ["status", "--porcelain=v1"],
        context="sentinel regression",
    )

    assert discovered_root == intended_repository.resolve()
    assert "README.md" in status_text
    assert _git_run(sentinel_repository, ["status", "--short"]) == ""


def test_corpus_load_supports_a_separate_primary_git_directory(tmp_path: Path) -> None:
    """Primary-worktree discovery must not assume a physical root `.git` directory."""

    module = _module_load()
    repository = tmp_path / "repository"
    git_directory = tmp_path / "repository-admin.git"
    _separate_git_directory_repository_create(repository, git_directory)
    corpus_root = repository / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)

    case_list = module._corpus_case_list_load(corpus_path)

    assert case_list[0].working_directory == repository
    assert (repository / ".git").is_file()
    assert git_directory.is_dir()


@pytest.mark.parametrize("direct_kind", ["directory", "symlink"])
def test_working_directory_rejects_an_existing_direct_target_on_another_branch(
    tmp_path: Path,
    direct_kind: str,
) -> None:
    """An existing direct path must not bypass same-branch worktree selection."""

    module = _module_load()
    source_repository = tmp_path / "source"
    target_repository = tmp_path / "target"
    _repository_create(source_repository)
    _repository_create(target_repository)
    task_branch = "2026-07-30-behavior-eval"
    source_task_root = source_repository / ".worktree" / task_branch
    _git_run(source_repository, ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"])
    corpus_root = source_task_root / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    if direct_kind == "directory":
        working_directory_value = str(target_repository)
    else:
        direct_link = corpus_root / "target-link"
        direct_link.symlink_to(target_repository, target_is_directory=True)
        working_directory_value = "target-link"

    with pytest.raises(module.SkillBehaviorEvalError, match="does not match corpus branch"):
        module._working_directory_resolve(
            corpus_path.resolve(),
            working_directory_value,
            context="wrong-branch direct target",
        )


def test_corpus_load_maps_a_sibling_repository_to_the_same_branch_worktree(tmp_path: Path) -> None:
    """A linked-worktree corpus must not resolve a sibling case back to main."""

    module = _module_load()
    source_repository = tmp_path / "source"
    target_repository = tmp_path / "target"
    _repository_create(source_repository)
    _repository_create(target_repository)
    task_branch = "2026-07-30-behavior-eval"
    source_task_root = source_repository / ".worktree" / task_branch
    target_task_root = target_repository / ".worktree" / task_branch
    _git_run(source_repository, ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"])
    _git_run(target_repository, ["worktree", "add", "-b", task_branch, str(target_task_root), "HEAD"])
    corpus_root = source_task_root / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    payload["case_list"][0]["working_directory"] = "../../target"
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")

    case = module._corpus_case_list_load(corpus_path)[0]

    assert case.working_directory == target_task_root.resolve()
    assert _git_run(case.working_directory, ["branch", "--show-current"]) == task_branch


def test_corpus_load_rejects_a_same_branch_subdirectory_symbolic_escape(tmp_path: Path) -> None:
    """A target subdirectory must remain physically inside the selected worktree."""

    module = _module_load()
    source_repository = tmp_path / "source"
    target_repository = tmp_path / "target"
    external_directory = tmp_path / "external"
    _repository_create(source_repository)
    _repository_create(target_repository)
    (target_repository / "subdir").mkdir()
    (target_repository / "subdir" / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _git_run(target_repository, ["add", "subdir/tracked.txt"])
    _git_run(target_repository, ["commit", "-m", "Add target subdirectory"])
    task_branch = "2026-07-30-behavior-eval"
    source_task_root = source_repository / ".worktree" / task_branch
    target_task_root = target_repository / ".worktree" / task_branch
    _git_run(source_repository, ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"])
    _git_run(target_repository, ["worktree", "add", "-b", task_branch, str(target_task_root), "HEAD"])
    corpus_root = source_task_root / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    payload["case_list"][0]["working_directory"] = "../../target/subdir"
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")
    external_directory.mkdir()
    (target_task_root / "subdir" / "tracked.txt").unlink()
    (target_task_root / "subdir").rmdir()
    (target_task_root / "subdir").symlink_to(external_directory, target_is_directory=True)

    with pytest.raises(module.SkillBehaviorEvalError, match="escapes its worktree"):
        module._corpus_case_list_load(corpus_path)


def test_corpus_load_rejects_a_symbolically_replaced_registered_worktree(tmp_path: Path) -> None:
    """A stale registered path cannot redirect selection to an unrelated repository."""

    module = _module_load()
    source_repository = tmp_path / "source"
    target_repository = tmp_path / "target"
    unrelated_repository = tmp_path / "unrelated"
    _repository_create(source_repository)
    _repository_create(target_repository)
    _repository_create(unrelated_repository)
    task_branch = "2026-07-30-behavior-eval"
    source_task_root = source_repository / ".worktree" / task_branch
    target_task_root = target_repository / ".worktree" / task_branch
    unrelated_task_root = unrelated_repository / ".worktree" / task_branch
    _git_run(source_repository, ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"])
    _git_run(target_repository, ["worktree", "add", "-b", task_branch, str(target_task_root), "HEAD"])
    _git_run(
        unrelated_repository,
        ["worktree", "add", "-b", task_branch, str(unrelated_task_root), "HEAD"],
    )
    corpus_root = source_task_root / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    payload["case_list"][0]["working_directory"] = "../../target"
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")
    displaced_target_root = tmp_path / "displaced-target-worktree"
    target_task_root.rename(displaced_target_root)
    target_task_root.symlink_to(unrelated_task_root, target_is_directory=True)

    with pytest.raises(module.SkillBehaviorEvalError, match="not one physical directory"):
        module._corpus_case_list_load(corpus_path)


def test_corpus_load_rejects_a_sibling_without_the_same_branch_worktree(tmp_path: Path) -> None:
    """A cross-repository case must never silently execute in the target main worktree."""

    module = _module_load()
    source_repository = tmp_path / "source"
    target_repository = tmp_path / "target"
    _repository_create(source_repository)
    _repository_create(target_repository)
    task_branch = "2026-07-30-behavior-eval"
    source_task_root = source_repository / ".worktree" / task_branch
    _git_run(source_repository, ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"])
    corpus_root = source_task_root / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    payload["case_list"][0]["working_directory"] = "../../target"
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(module.SkillBehaviorEvalError, match="expected exactly one target worktree"):
        module._corpus_case_list_load(corpus_path)


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


def test_corpus_load_normalizes_invalid_utf8(tmp_path: Path) -> None:
    """Invalid corpus encoding must remain inside the runner error boundary."""

    module = _module_load()
    corpus_path = tmp_path / "corpus-v1.json"
    corpus_path.write_bytes(b"\xff")

    with pytest.raises(module.SkillBehaviorEvalError, match="cannot load corpus"):
        module._corpus_case_list_load(corpus_path)


def test_git_repository_root_preserves_non_utf8_filesystem_text(tmp_path: Path) -> None:
    """Git discovery must decode valid filesystem bytes with surrogateescape."""

    module = _module_load()
    initial_repository = tmp_path / "repository"
    _repository_create(initial_repository)
    repository = Path(os.fsdecode(os.fsencode(tmp_path) + b"/repository-\xff"))
    initial_repository.rename(repository)

    assert module._git_repository_root_get(repository, context="non-UTF-8 root") == repository.resolve()


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
