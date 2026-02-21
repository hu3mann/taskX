"""Tests for worktree startup workflow."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from taskx.git.worktree import start_worktree
from taskx.obs.run_artifacts import DIRTY_STATE_FILENAME, WORKTREE_FILENAME


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repo_with_origin(tmp_path: Path) -> Path:
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")

    (repo / "README.md").write_text("# test\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "branch", "-M", "main")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-u", "origin", "main")
    return repo


def test_start_worktree_creates_branch_worktree_and_artifact(repo_with_origin: Path) -> None:
    repo = repo_with_origin
    run_dir = repo / "out" / "runs" / "RUN_100"
    run_dir.mkdir(parents=True)
    target_worktree = repo / "out" / "worktrees" / "RUN_100"

    report = start_worktree(
        run_dir=run_dir,
        repo_root=repo,
        branch="taskx/run-100",
        worktree_path=target_worktree,
        dirty_policy="refuse",
    )

    assert report["status"] == "passed"
    artifact_path = run_dir / WORKTREE_FILENAME
    assert artifact_path.exists()

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["branch"] == "taskx/run-100"
    assert Path(artifact["worktree_path"]).resolve() == target_worktree.resolve()
    assert target_worktree.exists()
    assert "taskx/run-100" in _git(repo, "branch", "--list", "taskx/run-100")


def test_start_worktree_stashes_when_dirty_policy_is_stash(repo_with_origin: Path) -> None:
    repo = repo_with_origin
    run_dir = repo / "out" / "runs" / "RUN_101"
    run_dir.mkdir(parents=True)

    (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    report = start_worktree(
        run_dir=run_dir,
        repo_root=repo,
        branch="taskx/run-101",
        worktree_path=repo / "out" / "worktrees" / "RUN_101",
        dirty_policy="stash",
    )

    assert report["status"] == "passed"
    dirty_state_path = run_dir / DIRTY_STATE_FILENAME
    assert dirty_state_path.exists()

    dirty_state = json.loads(dirty_state_path.read_text(encoding="utf-8"))
    assert dirty_state["events"]
    assert dirty_state["events"][0]["action"] == "stash"
    assert "dirty.txt" in "\n".join(dirty_state["events"][0]["changed_files"])
    assert "taskx:wt-start:RUN_101" in _git(repo, "stash", "list")
