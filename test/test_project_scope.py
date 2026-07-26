"""Behavior tests for canonical all and changed repository path scopes."""

from __future__ import annotations

from pathlib import Path
import subprocess

from project_standards.project_scope import project_relpath_list_get


def _git_commit(project_root: Path, message: str) -> None:
    """Commit all staged changes with isolated fixture identity.

    Args:
        project_root: Exact fixture Git worktree.
        message: Commit message.
    """

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
            message,
        ],
        check=True,
        cwd=project_root,
    )


def _git_init(project_root: Path) -> None:
    """Initialize one fixture Git repository.

    Args:
        project_root: Directory to initialize.
    """

    project_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], check=True, cwd=project_root)


def test_changed_scope_includes_staged_unstaged_rename_delete_and_untracked_paths(tmp_path: Path) -> None:
    """Every Git-visible change shape appears once in deterministic changed scope.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "project"
    _git_init(project_root)
    for file_name in ("deleted.py", "renamed.py", "staged.py", "unstaged.py"):
        (project_root / file_name).write_text(f"{file_name}\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], check=True, cwd=project_root)
    _git_commit(project_root, "base")

    (project_root / "staged.py").write_text("staged change\n", encoding="utf-8")
    subprocess.run(["git", "add", "staged.py"], check=True, cwd=project_root)
    (project_root / "unstaged.py").write_text("unstaged change\n", encoding="utf-8")
    subprocess.run(["git", "mv", "renamed.py", "moved.py"], check=True, cwd=project_root)
    subprocess.run(["git", "rm", "-q", "deleted.py"], check=True, cwd=project_root)
    (project_root / "untracked.py").write_text("untracked\n", encoding="utf-8")

    assert project_relpath_list_get(project_root, scope="changed") == [
        "deleted.py",
        "moved.py",
        "renamed.py",
        "staged.py",
        "unstaged.py",
        "untracked.py",
    ]
    assert project_relpath_list_get(project_root, scope="all") == [
        "moved.py",
        "staged.py",
        "unstaged.py",
        "untracked.py",
    ]


def test_changed_scope_expands_changed_gitlink_and_direct_submodule_dirty_state(tmp_path: Path) -> None:
    """Changed gitlinks and direct-submodule worktree changes expose owned paths.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "consumer"
    submodule_root = project_root / "provider"
    _git_init(submodule_root)
    (submodule_root / "changed.py").write_text("base\n", encoding="utf-8")
    (submodule_root / "unchanged.py").write_text("stable\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], check=True, cwd=submodule_root)
    _git_commit(submodule_root, "provider base")
    base_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        check=True,
        cwd=submodule_root,
        text=True,
    ).stdout.strip()

    (submodule_root / "changed.py").write_text("next\n", encoding="utf-8")
    subprocess.run(["git", "add", "changed.py"], check=True, cwd=submodule_root)
    _git_commit(submodule_root, "provider next")

    _git_init(project_root)
    (project_root / ".gitmodules").write_text(
        '[submodule "provider"]\n\tpath = provider\n\turl = https://example.invalid/provider.git\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", ".gitmodules"], check=True, cwd=project_root)
    subprocess.run(
        ["git", "update-index", "--add", "--cacheinfo", f"160000,{base_revision},provider"],
        check=True,
        cwd=project_root,
    )
    _git_commit(project_root, "consumer base")

    (submodule_root / "dirty.py").write_text("dirty\n", encoding="utf-8")
    (submodule_root / "unchanged.py").write_text("worktree change\n", encoding="utf-8")

    assert project_relpath_list_get(project_root, scope="changed") == [
        "provider",
        "provider/changed.py",
        "provider/dirty.py",
        "provider/unchanged.py",
    ]


def test_changed_scope_uses_current_submodule_paths_when_gitlink_commit_is_unavailable(tmp_path: Path) -> None:
    """An unavailable gitlink base expands to every current Submodule path.

    Args:
        tmp_path: Pytest temporary directory.
    """

    project_root = tmp_path / "consumer"
    submodule_root = project_root / "provider"
    _git_init(submodule_root)
    (submodule_root / "first.py").write_text("first\n", encoding="utf-8")
    (submodule_root / "second.py").write_text("second\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], check=True, cwd=submodule_root)
    _git_commit(submodule_root, "provider")

    _git_init(project_root)
    (project_root / ".gitmodules").write_text(
        '[submodule "provider"]\n\tpath = provider\n\turl = https://example.invalid/provider.git\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", ".gitmodules"], check=True, cwd=project_root)
    unavailable_revision = "1" * 40
    subprocess.run(
        ["git", "update-index", "--add", "--cacheinfo", f"160000,{unavailable_revision},provider"],
        check=True,
        cwd=project_root,
    )
    _git_commit(project_root, "consumer")

    assert project_relpath_list_get(project_root, scope="changed") == [
        "provider",
        "provider/first.py",
        "provider/second.py",
    ]
