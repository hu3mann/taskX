"""Tests for finish_run rebase-ff workflow."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from taskx.git.finish import finish_run
from taskx.git.worktree import start_worktree
from taskx.obs.run_artifacts import FINISH_FILENAME, WORKTREE_FILENAME


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


def _worktree_path(run_dir: Path) -> Path:
    payload = json.loads((run_dir / WORKTREE_FILENAME).read_text(encoding="utf-8"))
    return Path(payload["worktree_path"]).resolve()


def test_finish_run_rebase_ff_push_and_cleanup(repo_with_origin: Path) -> None:
    repo = repo_with_origin
    run_dir = repo / "out" / "runs" / "RUN_FINISH"
    run_dir.mkdir(parents=True)

    start_report = start_worktree(
        run_dir=run_dir,
        repo_root=repo,
        branch="taskx/run-finish",
        worktree_path=repo / "out" / "worktrees" / "RUN_FINISH",
        dirty_policy="refuse",
    )
    assert start_report["status"] == "passed"

    worktree = _worktree_path(run_dir)
    (worktree / "feature.txt").write_text("task branch update\n", encoding="utf-8")
    _git(worktree, "add", "feature.txt")
    _git(worktree, "commit", "-m", "task branch change")

    (repo / "main-only.txt").write_text("main branch update\n", encoding="utf-8")
    _git(repo, "add", "main-only.txt")
    _git(repo, "commit", "-m", "main branch change")
    _git(repo, "push", "origin", "main")

    report = finish_run(
        run_dir=run_dir,
        mode="rebase-ff",
        cleanup=True,
        dirty_policy="refuse",
        remote="origin",
    )

    assert report["status"] == "passed"
    assert report["verification"]["main_matches_remote"] is True
    assert (run_dir / FINISH_FILENAME).exists()

    local_main = _git(repo, "rev-parse", "main")
    origin_main = _git(repo, "rev-parse", "origin/main")
    assert local_main == origin_main

    assert not worktree.exists()
    assert _git(repo, "branch", "--list", "taskx/run-finish") == ""
    assert "task branch change" in _git(repo, "log", "--pretty=%s", "-n", "5")
