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
ACCEPTANCE_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins/project-standards/skills/project-instruction-developer/scripts/skill_behavior_acceptance.py"
)
CORPUS_PATH = Path(__file__).resolve().parents[1] / "skill_behavior_eval/corpus-v1.json"


def _module_load() -> ModuleType:
    """Load the script as one isolated module.

    Returns:
        The script as one isolated module.
    """

    spec = importlib.util.spec_from_file_location("skill_behavior_eval", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _acceptance_module_load() -> ModuleType:
    """Load the failed-subset acceptance planner as one isolated module."""

    spec = importlib.util.spec_from_file_location("skill_behavior_acceptance", ACCEPTANCE_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {ACCEPTANCE_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _acceptance_result_payload(
    case_id_list: list[str],
    *,
    failed_case_id_list: list[str],
) -> dict[str, Any]:
    """Build one minimal current runner result for convergence tests."""

    failed_case_id_set = set(failed_case_id_list)
    return {
        "schema_version": 2,
        "model": "gpt-5.6-sol",
        "reasoning_effort": "max",
        "case_result_list": [
            {
                "suite": case_id.split(":", maxsplit=1)[0],
                "id": case_id.split(":", maxsplit=1)[1],
                "passed": case_id not in failed_case_id_set,
            }
            for case_id in case_id_list
        ],
        "failed_case_id_list": failed_case_id_list,
    }


def test_acceptance_cycle_converges_only_through_remaining_failed_subset() -> None:
    """One cycle monotonically removes passes until the targeted result is empty."""

    module = _acceptance_module_load()
    first = _acceptance_result_payload(
        ["provider:case-a", "provider:case-b", "provider:case-c"],
        failed_case_id_list=["provider:case-b", "provider:case-c"],
    )
    second = _acceptance_result_payload(
        ["provider:case-b", "provider:case-c"],
        failed_case_id_list=["provider:case-c"],
    )
    third = _acceptance_result_payload(
        ["provider:case-c"],
        failed_case_id_list=[],
    )

    after_first = module.acceptance_state_get([first]).payload()
    after_second = module.acceptance_state_get([first, second]).payload()
    complete = module.acceptance_state_get([first, second, third]).payload()

    assert after_first["failed_case_id_list"] == ["provider:case-b", "provider:case-c"]
    assert after_first["next_case_argument_list"] == [
        "--case",
        "provider:case-b",
        "--case",
        "provider:case-c",
    ]
    assert after_second["failed_case_id_list"] == ["provider:case-c"]
    assert after_second["passed_case_id_list"] == ["provider:case-a", "provider:case-b"]
    assert complete["complete"] is True
    assert complete["failed_case_id_list"] == []
    assert complete["passed_case_id_list"] == [
        "provider:case-a",
        "provider:case-b",
        "provider:case-c",
    ]


def test_acceptance_cycle_finishes_on_first_zero_failure_result() -> None:
    """An initially clean selected set does not manufacture a targeted pass."""

    module = _acceptance_module_load()
    state = module.acceptance_state_get(
        [
            _acceptance_result_payload(
                ["provider:case-a", "provider:case-b"],
                failed_case_id_list=[],
            )
        ]
    )

    assert state.payload()["complete"] is True
    assert state.completed_iteration_count == 1
    assert state.payload()["next_case_argument_list"] == []


def test_acceptance_cycle_rejects_replanning_one_passed_case() -> None:
    """A passed case cannot re-enter a later targeted result in the same cycle."""

    module = _acceptance_module_load()
    first = _acceptance_result_payload(
        ["provider:case-a", "provider:case-b"],
        failed_case_id_list=["provider:case-b"],
    )
    repeated = _acceptance_result_payload(
        ["provider:case-a", "provider:case-b"],
        failed_case_id_list=[],
    )

    with pytest.raises(module.SkillBehaviorAcceptanceError, match="exactly the current failed case set"):
        module.acceptance_state_get([first, repeated])


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("model", "another-model"),
        ("reasoning_effort", "high"),
    ],
)
def test_acceptance_cycle_requires_exact_target_model_configuration(
    field_name: str,
    value: str,
) -> None:
    """Every initial and targeted result uses the same canonical model configuration."""

    module = _acceptance_module_load()
    result = _acceptance_result_payload(["provider:case-a"], failed_case_id_list=[])
    result[field_name] = value

    with pytest.raises(module.SkillBehaviorAcceptanceError, match="gpt-5.6-sol"):
        module.acceptance_state_get([result])


def test_acceptance_cycle_rejects_failed_list_that_differs_from_case_outcomes() -> None:
    """Scheduling consumes the exact runner failure set, not an unchecked summary."""

    module = _acceptance_module_load()
    result = _acceptance_result_payload(
        ["provider:case-a", "provider:case-b"],
        failed_case_id_list=["provider:case-b"],
    )
    result["failed_case_id_list"] = ["provider:case-a"]

    with pytest.raises(module.SkillBehaviorAcceptanceError, match="differs from its case outcomes"):
        module.acceptance_state_get([result])


def test_acceptance_cli_reports_exact_next_case_arguments(tmp_path: Path) -> None:
    """The reusable CLI turns immutable result JSON into direct repeated --case argv."""

    first_path = tmp_path / "run-0.json"
    first_path.write_text(
        json.dumps(
            _acceptance_result_payload(
                ["provider:case-a", "provider:case-b"],
                failed_case_id_list=["provider:case-b"],
            )
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(ACCEPTANCE_SCRIPT_PATH), "--result", str(first_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert completed.stderr == ""
    assert json.loads(completed.stdout)["next_case_argument_list"] == [
        "--case",
        "provider:case-b",
    ]


def test_runner_result_exposes_exact_failed_set_for_acceptance() -> None:
    """The model runner emits the suite-qualified subset consumed by the planner."""

    module = _module_load()
    result_list = [
        module.SkillBehaviorCaseResult(
            activated_skill_list=(),
            forbidden_activated_skill_list=(),
            id="case-a",
            missing_expected_skill_list=(),
            passed=True,
            response="accepted",
            semantic_invariant_result_list=(),
            suite="provider",
        ),
        module.SkillBehaviorCaseResult(
            activated_skill_list=(),
            forbidden_activated_skill_list=(),
            id="case-b",
            missing_expected_skill_list=(),
            passed=False,
            response="needs classification",
            semantic_invariant_result_list=(),
            suite="provider",
        ),
    ]

    payload = module._result_payload_get(
        invocation_config=module.ModelInvocationConfig(
            codex_bin="codex",
            model=module.DEFAULT_MODEL,
            reasoning_effort=module.DEFAULT_REASONING_EFFORT,
        ),
        result_list=result_list,
    )

    assert payload["schema_version"] == 2
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["reasoning_effort"] == "max"
    assert payload["failed_case_count"] == 1
    assert payload["failed_case_id_list"] == ["provider:case-b"]


def _corpus_write(path: Path, *, expected_skill_list: list[str] | None = None) -> None:
    """Write one minimal valid corpus.

    Args:
        path: Exact filesystem path.
        expected_skill_list: Expected skill list.
    """

    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "suite": "provider",
                "case_list": [
                    {
                        "id": "case-a",
                        "working_directory": "..",
                        "working_directory_mode": "same-branch",
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
    """Run one checked Git command in a test repository.

    Args:
        repository: Exact Git repository root.
        argument_list: Exact command arguments.

    Returns:
        Resulting text value.
    """

    result = subprocess.run(
        ["git", "-C", str(repository), *argument_list],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _repository_create(repository: Path) -> None:
    """Create one minimal main-branch test repository.

    Args:
        repository: Exact Git repository root.
    """

    repository.mkdir()
    _git_run(repository, ["init", "-b", "main"])
    _git_run(repository, ["config", "user.email", "test@example.com"])
    _git_run(repository, ["config", "user.name", "Behavior Eval Test"])
    (repository / "README.md").write_text("baseline\n", encoding="utf-8")
    _git_run(repository, ["add", "README.md"])
    _git_run(repository, ["commit", "-m", "Initial test state"])


def test_judge_prompt_evaluates_real_mutations_as_read_only_proposed_behavior(tmp_path: Path) -> None:
    """The judge cannot demand mutations that the generation sandbox explicitly forbids."""

    module = _module_load()
    case = module.SkillBehaviorCase(
        corpus_path=tmp_path / "corpus-v1.json",
        expected_skill_list=("project-standards:project-foundation",),
        forbidden_skill_list=(),
        id="mutation-contract",
        prompt="Atomically replace the validated destination.",
        semantic_invariant_list=(
            module.SemanticInvariant(
                id="atomic-replacement",
                text="The response writes one atomic complete replacement.",
            ),
        ),
        suite="provider",
        working_directory=tmp_path,
    )

    prompt = module._judge_prompt_get(
        case=case,
        generation_payload={
            "activated_skill_list": ["project-standards:project-foundation"],
            "response": "In a real run I would write one atomic complete replacement, but this evaluation is read-only.",
        },
    )

    assert "read-only behavior simulation" in prompt
    assert "correctly commits to that action for a real run" in prompt
    assert "do not require or reward performing it in this simulation" in prompt


def _separate_git_directory_repository_create(repository: Path, git_directory: Path) -> None:
    """Create one main worktree whose Git administration lives elsewhere.

    Args:
        repository: Exact Git repository root.
        git_directory: Git directory.
    """

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


def test_bundled_corpus_declares_each_working_directory_revision_policy() -> None:
    """The provider corpus must remain valid under its own closed case schema."""

    case_list = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["case_list"]
    synchronized_main_directory_set = {
        "../../compose-mysql",
        "../../scrapy-next-deprecated",
        "../../workflow-control-center",
    }

    assert case_list
    assert all(
        case["working_directory_mode"]
        == ("synchronized-main" if case["working_directory"] in synchronized_main_directory_set else "same-branch")
        for case in case_list
    )


def test_corpus_load_resolves_working_directory(tmp_path: Path) -> None:
    """A valid corpus should resolve its repository-relative working directory.

    Args:
        tmp_path: Temporary directory path.
    """

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


def test_case_selection_does_not_resolve_unselected_runtime_root(
    tmp_path: Path,
) -> None:
    """A focused task-worktree eval must not require unrelated repository worktrees.

    Args:
        tmp_path: Temporary directory path.
    """

    module = _module_load()
    repository = tmp_path / "repository"
    _repository_create(repository)
    corpus_root = repository / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    unavailable_case = dict(payload["case_list"][0])
    unavailable_case["id"] = "case-unavailable"
    unavailable_case["working_directory"] = "../../unavailable-repository"
    payload["case_list"].append(unavailable_case)
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")

    selected = module._selected_case_list_get(
        case_id_list=["case-a"],
        corpus_path_list=[corpus_path],
    )

    assert [case.id for case in selected] == ["case-a"]
    with pytest.raises(module.SkillBehaviorEvalError):
        module._selected_case_list_get(case_id_list=[], corpus_path_list=[corpus_path])


def test_corpus_load_rejects_boolean_schema_version(tmp_path: Path) -> None:
    """A boolean must not alias the integer version in the closed corpus schema.

    Args:
        tmp_path: Temporary directory path.
    """

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
    """Repository discovery must not honor caller-controlled Git redirect state.

    Args:
        monkeypatch: Pytest mutation fixture.
        tmp_path: Temporary directory path.
    """

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
    """Primary-worktree discovery must not assume a physical root `.git` directory.

    Args:
        tmp_path: Temporary directory path.
    """

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
    """An existing direct path must not bypass same-branch worktree selection.

    Args:
        tmp_path: Temporary directory path.
        direct_kind: Direct kind.
    """

    module = _module_load()
    source_repository = tmp_path / "source"
    target_repository = tmp_path / "target"
    _repository_create(source_repository)
    _repository_create(target_repository)
    task_branch = "2026-07-30-behavior-eval"
    source_task_root = source_repository / ".worktree" / task_branch
    _git_run(
        source_repository,
        ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"],
    )
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
            mode="same-branch",
        )


def test_corpus_load_maps_a_sibling_repository_to_the_same_branch_worktree(
    tmp_path: Path,
) -> None:
    """A linked-worktree corpus must not resolve a sibling case back to main.

    Args:
        tmp_path: Temporary directory path.
    """

    module = _module_load()
    source_repository = tmp_path / "source"
    target_repository = tmp_path / "target"
    _repository_create(source_repository)
    _repository_create(target_repository)
    task_branch = "2026-07-30-behavior-eval"
    source_task_root = source_repository / ".worktree" / task_branch
    target_task_root = target_repository / ".worktree" / task_branch
    _git_run(
        source_repository,
        ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"],
    )
    _git_run(
        target_repository,
        ["worktree", "add", "-b", task_branch, str(target_task_root), "HEAD"],
    )
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


def test_corpus_load_rejects_a_same_branch_subdirectory_symbolic_escape(
    tmp_path: Path,
) -> None:
    """A target subdirectory must remain physically inside the selected worktree.

    Args:
        tmp_path: Temporary directory path.
    """

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
    _git_run(
        source_repository,
        ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"],
    )
    _git_run(
        target_repository,
        ["worktree", "add", "-b", task_branch, str(target_task_root), "HEAD"],
    )
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


def test_corpus_load_rejects_a_symbolically_replaced_registered_worktree(
    tmp_path: Path,
) -> None:
    """A stale registered path cannot redirect selection to an unrelated repository.

    Args:
        tmp_path: Temporary directory path.
    """

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
    _git_run(
        source_repository,
        ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"],
    )
    _git_run(
        target_repository,
        ["worktree", "add", "-b", task_branch, str(target_task_root), "HEAD"],
    )
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


def test_corpus_load_rejects_a_sibling_without_the_same_branch_worktree(
    tmp_path: Path,
) -> None:
    """A cross-repository case must never silently execute in the target main worktree.

    Args:
        tmp_path: Temporary directory path.
    """

    module = _module_load()
    source_repository = tmp_path / "source"
    target_repository = tmp_path / "target"
    _repository_create(source_repository)
    _repository_create(target_repository)
    task_branch = "2026-07-30-behavior-eval"
    source_task_root = source_repository / ".worktree" / task_branch
    _git_run(
        source_repository,
        ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"],
    )
    corpus_root = source_task_root / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    payload["case_list"][0]["working_directory"] = "../../target"
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(module.SkillBehaviorEvalError, match="expected exactly one target worktree"):
        module._corpus_case_list_load(corpus_path)


def test_corpus_load_enforces_an_explicit_synchronized_main_dependency(
    tmp_path: Path,
) -> None:
    """A non-participant target must use the clean synchronized canonical main worktree.

    Args:
        tmp_path: Temporary directory path.
    """

    module = _module_load()
    source_repository = tmp_path / "source"
    target_repository = tmp_path / "target"
    target_origin = tmp_path / "target-origin.git"
    _repository_create(source_repository)
    _repository_create(target_repository)
    (target_repository / "domain").mkdir()
    (target_repository / "domain" / "owner.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git_run(target_repository, ["add", "domain/owner.py"])
    _git_run(target_repository, ["commit", "-m", "Add target owner"])
    _git_run(tmp_path, ["init", "--bare", str(target_origin)])
    _git_run(target_repository, ["remote", "add", "origin", str(target_origin)])
    _git_run(target_repository, ["push", "--set-upstream", "origin", "main"])
    task_branch = "2026-07-30-behavior-eval"
    source_task_root = source_repository / ".worktree" / task_branch
    target_task_root = tmp_path / "target-task-root"
    _git_run(
        source_repository,
        ["worktree", "add", "-b", task_branch, str(source_task_root), "HEAD"],
    )
    _git_run(
        target_repository,
        ["worktree", "add", "-b", task_branch, str(target_task_root), "HEAD"],
    )
    corpus_root = source_task_root / "skill_behavior_eval"
    corpus_root.mkdir()
    corpus_path = corpus_root / "corpus-v1.json"
    _corpus_write(corpus_path)
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    payload["case_list"][0]["working_directory"] = "../../target/domain"
    payload["case_list"][0]["working_directory_mode"] = "synchronized-main"
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")

    case = module._corpus_case_list_load(corpus_path)[0]

    assert case.working_directory == (target_repository / "domain").resolve()
    (target_repository / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    with pytest.raises(module.SkillBehaviorEvalError, match="target main worktree is not clean"):
        module._corpus_case_list_load(corpus_path)
    (target_repository / "dirty.txt").unlink()
    (target_repository / "README.md").write_text("diverged\n", encoding="utf-8")
    _git_run(target_repository, ["add", "README.md"])
    _git_run(target_repository, ["commit", "-m", "Diverge target main"])
    with pytest.raises(module.SkillBehaviorEvalError, match="target main does not equal origin/main"):
        module._corpus_case_list_load(corpus_path)


def test_corpus_load_rejects_activation_overlap(tmp_path: Path) -> None:
    """One skill cannot be both expected and forbidden.

    Args:
        tmp_path: Temporary directory path.
    """

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
    """Invalid corpus encoding must remain inside the runner error boundary.

    Args:
        tmp_path: Temporary directory path.
    """

    module = _module_load()
    corpus_path = tmp_path / "corpus-v1.json"
    corpus_path.write_bytes(b"\xff")

    with pytest.raises(module.SkillBehaviorEvalError, match="cannot load corpus"):
        module._corpus_case_list_load(corpus_path)


def test_git_repository_root_preserves_non_utf8_filesystem_text(tmp_path: Path) -> None:
    """Git discovery must decode valid filesystem bytes with surrogateescape.

    Args:
        tmp_path: Temporary directory path.
    """

    module = _module_load()
    initial_repository = tmp_path / "repository"
    _repository_create(initial_repository)
    repository = Path(os.fsdecode(os.fsencode(tmp_path) + b"/repository-\xff"))
    initial_repository.rename(repository)

    assert module._git_repository_root_get(repository, context="non-UTF-8 root") == repository.resolve()


def test_case_evaluate_combines_activation_and_independent_judge(
    tmp_path: Path,
) -> None:
    """Case success should require expected activation and every semantic invariant.

    Args:
        tmp_path: Temporary directory path.
    """

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
        """Return generation first and judge output second.

        Args:
            prompt: Prompt.
            working_directory: Working directory.
            output_schema: Output schema.
            invocation_config: Invocation config.

        Returns:
            The scripted generation result followed by the judge result.
        """

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
        ),
        model_call=_model_call,
    )

    assert result.passed is True
    assert result.missing_expected_skill_list == ()
    assert len(call_list) == 2
    assert "Do not use keyword" in call_list[1]["prompt"]


def test_case_evaluate_reports_missing_and_forbidden_activations(
    tmp_path: Path,
) -> None:
    """Activation failures should be independent from a passing semantic judge.

    Args:
        tmp_path: Temporary directory path.
    """

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
        ),
        model_call=lambda *_args: next(payload_list),
    )

    assert result.passed is False
    assert result.missing_expected_skill_list == ("project-standards:python-developer",)
    assert result.forbidden_activated_skill_list == ("agent-workflows:code-audit",)


def test_activation_normalization_requires_one_unambiguous_provider_identity(
    tmp_path: Path,
) -> None:
    """A short self-report should canonicalize only against one exact case identity.

    Args:
        tmp_path: Temporary directory path.
    """

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
    """Concurrent completion order must not change the serialized corpus order.

    Args:
        monkeypatch: Pytest mutation fixture.
        tmp_path: Temporary directory path.
    """

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
        """Return the second case first.

        Args:
            case: Case.
            invocation_config: Invocation config.

        Returns:
            The second case first.
        """

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
        ),
    )

    assert [result.id for result in result_list] == ["case-a", "case-b"]


def _plugin_binding_fixture_create(
    tmp_path: Path,
    *,
    source: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """Create one source marketplace and matching server-prepared cache fixture."""

    marketplace_name = "provider-marketplace"
    plugin_name = "project-standards"
    plugin_version = "0.1.0+codex.test"
    marketplace_path = tmp_path / "provider-worktree"
    plugin_source = source or {"source": "local", "path": f"./plugins/{plugin_name}"}
    marketplace_manifest_path = marketplace_path / ".agents/plugins/marketplace.json"
    marketplace_manifest_path.parent.mkdir(parents=True)
    marketplace_manifest_path.write_text(
        json.dumps(
            {
                "name": marketplace_name,
                "plugins": [{"name": plugin_name, "source": plugin_source}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    standard_codex_home = tmp_path / "os-user-home/.codex"
    standard_codex_home.mkdir(parents=True)
    if plugin_source == {"source": "local", "path": f"./plugins/{plugin_name}"}:
        source_plugin_path = marketplace_path / f"plugins/{plugin_name}"
        source_manifest_path = source_plugin_path / ".codex-plugin/plugin.json"
        source_manifest_path.parent.mkdir(parents=True)
        source_manifest_path.write_text(
            json.dumps({"name": plugin_name, "version": plugin_version}) + "\n",
            encoding="utf-8",
        )
        (source_plugin_path / "SKILL.md").write_text("source\n", encoding="utf-8")
        cache_plugin_path = standard_codex_home / f"plugins/cache/{marketplace_name}/{plugin_name}/{plugin_version}"
        cache_manifest_path = cache_plugin_path / ".codex-plugin/plugin.json"
        cache_manifest_path.parent.mkdir(parents=True)
        cache_manifest_path.write_bytes(source_manifest_path.read_bytes())
        (cache_plugin_path / "SKILL.md").write_text("source\n", encoding="utf-8")
    return marketplace_path, standard_codex_home


def test_standard_codex_environment_preserves_real_home_and_unset_override(tmp_path: Path) -> None:
    """The evaluator forwards one unchanged standard-home process environment."""

    module = _module_load()
    os_user_home = tmp_path / "os-user-home"
    (os_user_home / ".codex").mkdir(parents=True)
    environment = {"HOME": str(os_user_home), "PATH": "/usr/bin"}

    assert (
        module._standard_codex_process_environment_get(
            environment,
            os_user_home=os_user_home,
        )
        == environment
    )


@pytest.mark.parametrize(
    "environment_update",
    [
        {"HOME": "/another-home"},
        {"CODEX_HOME": ""},
        {"CODEX_HOME": "/another-codex-home"},
    ],
)
def test_standard_codex_environment_rejects_home_substitution(
    tmp_path: Path,
    environment_update: dict[str, str],
) -> None:
    """HOME substitution and any CODEX_HOME value fail before Codex launch."""

    module = _module_load()
    os_user_home = tmp_path / "os-user-home"
    (os_user_home / ".codex").mkdir(parents=True)
    environment = {"HOME": str(os_user_home), **environment_update}

    with pytest.raises(module.SkillBehaviorEvalError, match="HOME|CODEX_HOME"):
        module._standard_codex_process_environment_get(
            environment,
            os_user_home=os_user_home,
        )


def test_codex_invocation_uses_standard_home_persistent_session_and_native_wait(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The launcher keeps history, forwards standard state and sets no project timeout."""

    module = _module_load()
    environment = {"HOME": "/home/test-user", "PATH": "/usr/bin"}
    run_call_list: list[tuple[list[str], dict[str, Any]]] = []

    def _run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        run_call_list.append((command, kwargs))
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"response":"ok"}\n', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(module, "_standard_codex_process_environment_get", lambda: environment)
    monkeypatch.setattr(module.subprocess, "run", _run)

    assert module._codex_payload_get(
        "prompt",
        tmp_path,
        {"type": "object"},
        module.ModelInvocationConfig(codex_bin="codex", model="gpt-5.6-sol", reasoning_effort="max"),
    ) == {"response": "ok"}
    command, run_keyword_by_name_map = run_call_list[0]
    assert "--ephemeral" not in command
    assert "--ignore-user-config" not in command
    assert "history.persistence" not in command
    assert run_keyword_by_name_map["env"] == environment
    assert "CODEX_HOME" not in run_keyword_by_name_map["env"]
    assert "timeout" not in run_keyword_by_name_map


def test_preinstalled_plugin_binding_accepts_exact_server_cache(tmp_path: Path) -> None:
    """Evaluation accepts one exact source already prepared in the standard home."""

    module = _module_load()
    marketplace_path, standard_codex_home = _plugin_binding_fixture_create(tmp_path)
    corpus_path = tmp_path / "corpus.json"
    _corpus_write(corpus_path)

    module._preinstalled_plugin_source_binding_validate(
        case_list=module._selected_case_list_get(case_id_list=[], corpus_path_list=[corpus_path]),
        marketplace_path_list=[marketplace_path],
        plugin_selector_list=["project-standards@provider-marketplace"],
        standard_codex_home=standard_codex_home,
    )


def test_preinstalled_plugin_binding_ignores_runtime_bytecode_cache(tmp_path: Path) -> None:
    """Runtime bytecode is worker state and cannot become provider source identity."""

    module = _module_load()
    marketplace_path, standard_codex_home = _plugin_binding_fixture_create(tmp_path)
    source_bytecode_path = marketplace_path / "plugins/project-standards/__pycache__/source.cpython-314.pyc"
    source_bytecode_path.parent.mkdir()
    source_bytecode_path.write_bytes(b"source-runtime-cache")
    cache_bytecode_path = next(standard_codex_home.glob("plugins/cache/*/*/*")) / "__pycache__/source.cpython-314.pyc"
    cache_bytecode_path.parent.mkdir()
    cache_bytecode_path.write_bytes(b"installed-runtime-cache")

    module._preinstalled_plugin_source_binding_validate(
        case_list=[],
        marketplace_path_list=[marketplace_path],
        plugin_selector_list=["project-standards@provider-marketplace"],
        standard_codex_home=standard_codex_home,
    )


def test_preinstalled_plugin_binding_rejects_cache_drift(tmp_path: Path) -> None:
    """A stale or different server cache cannot stand in for the declared source."""

    module = _module_load()
    marketplace_path, standard_codex_home = _plugin_binding_fixture_create(tmp_path)
    cache_skill_path = next(standard_codex_home.glob("plugins/cache/*/*/*/SKILL.md"))
    cache_skill_path.write_text("different\n", encoding="utf-8")

    with pytest.raises(module.SkillBehaviorEvalError, match="differs from its declared source"):
        module._preinstalled_plugin_source_binding_validate(
            case_list=[],
            marketplace_path_list=[marketplace_path],
            plugin_selector_list=["project-standards@provider-marketplace"],
            standard_codex_home=standard_codex_home,
        )


def test_preinstalled_plugin_binding_rejects_partial_source_binding(tmp_path: Path) -> None:
    """A source declaration without exact plugin selectors fails closed."""

    module = _module_load()

    with pytest.raises(module.SkillBehaviorEvalError, match="must be supplied together"):
        module._preinstalled_plugin_source_binding_validate(
            case_list=[],
            marketplace_path_list=[tmp_path / "provider-worktree"],
            plugin_selector_list=[],
            standard_codex_home=tmp_path / "os-user-home/.codex",
        )


def test_preinstalled_plugin_binding_rejects_selector_outside_provided_marketplace(tmp_path: Path) -> None:
    """A selector cannot resolve from an undeclared server marketplace."""

    module = _module_load()
    marketplace_path, standard_codex_home = _plugin_binding_fixture_create(tmp_path)

    with pytest.raises(module.SkillBehaviorEvalError, match="unprovided marketplace"):
        module._preinstalled_plugin_source_binding_validate(
            case_list=[],
            marketplace_path_list=[marketplace_path],
            plugin_selector_list=["project-standards@another-marketplace"],
            standard_codex_home=standard_codex_home,
        )


@pytest.mark.parametrize(
    ("source", "error_pattern"),
    [
        ({"source": "git", "url": "https://example.invalid/provider.git"}, "must be one local path"),
        ({"source": "local", "path": "../outside-plugin"}, "escapes its provided marketplace"),
    ],
)
def test_preinstalled_plugin_binding_rejects_non_worktree_plugin_source(
    tmp_path: Path,
    source: dict[str, str],
    error_pattern: str,
) -> None:
    """A declared source cannot redirect the server binding outside its worktree."""

    module = _module_load()
    marketplace_path, standard_codex_home = _plugin_binding_fixture_create(tmp_path, source=source)

    with pytest.raises(module.SkillBehaviorEvalError, match=error_pattern):
        module._preinstalled_plugin_source_binding_validate(
            case_list=[],
            marketplace_path_list=[marketplace_path],
            plugin_selector_list=["project-standards@provider-marketplace"],
            standard_codex_home=standard_codex_home,
        )


def test_expected_plugin_source_binding_rejects_an_omitted_provider(
    tmp_path: Path,
) -> None:
    """An isolated run must install every provider expected by its selected cases.

    Args:
        tmp_path: Temporary directory path.
    """

    module = _module_load()
    corpus_path = tmp_path / "corpus.json"
    _corpus_write(
        corpus_path,
        expected_skill_list=[
            "agent-workflows:goal-brainstorm",
            "workflow-container-agent-tools:workflow-container-developer",
        ],
    )
    case_list = module._selected_case_list_get(
        case_id_list=[],
        corpus_path_list=[corpus_path],
    )

    with pytest.raises(
        module.SkillBehaviorEvalError,
        match="workflow-container-agent-tools",
    ):
        module._expected_plugin_source_binding_validate(
            case_list,
            ["agent-workflows@agent-plugins"],
        )


def test_expected_plugin_source_binding_accepts_complete_provider_set(
    tmp_path: Path,
) -> None:
    """Extra marketplaces may coexist with a complete expected provider set.

    Args:
        tmp_path: Temporary directory path.
    """

    module = _module_load()
    corpus_path = tmp_path / "corpus.json"
    _corpus_write(
        corpus_path,
        expected_skill_list=["project-standards:python-developer"],
    )
    case_list = module._selected_case_list_get(
        case_id_list=[],
        corpus_path_list=[corpus_path],
    )

    module._expected_plugin_source_binding_validate(
        case_list,
        [
            "project-standards@project-standards",
            "agent-workflows@agent-plugins",
        ],
    )
