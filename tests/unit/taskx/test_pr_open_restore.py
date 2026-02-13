"""Restore rail tests for assisted PR open flow."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

import taskx.pr.open as pr_open_module
from taskx.pr.open import run_pr_open

if TYPE_CHECKING:
    from pathlib import Path


def _run(cmd: list[str], *, cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _init_repo_with_origin(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(remote), "repo"], cwd=workspace, check=True, capture_output=True)

    repo = workspace / "repo"
    _run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test User"], cwd=repo)
    _run(["git", "checkout", "-b", "main"], cwd=repo)

    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=repo)
    _run(["git", "commit", "-m", "init"], cwd=repo)
    _run(["git", "push", "-u", "origin", "main"], cwd=repo)
    _run(["git", "checkout", "-b", "feature/pr-flow"], cwd=repo)

    (repo / "feature.txt").write_text("change\n", encoding="utf-8")
    _run(["git", "add", "feature.txt"], cwd=repo)
    _run(["git", "commit", "-m", "feature"], cwd=repo)
    return repo


def test_pr_open_restores_branch_after_success(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo_with_origin(tmp_path)
    body_file = tmp_path / "PR_BODY.md"
    body_file.write_text("PR body\n", encoding="utf-8")

    original_branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)

    monkeypatch.setattr("taskx.pr.open.shutil.which", lambda _name: None)
    original_git_output = pr_open_module._git_output

    def _patched_git_output(repo_root, args):  # type: ignore[no-untyped-def]
        if args == ["remote", "get-url", "origin"]:
            return "https://github.com/acme/taskX.git"
        return original_git_output(repo_root, args)

    monkeypatch.setattr("taskx.pr.open._git_output", _patched_git_output)

    report = run_pr_open(
        repo_root=repo,
        title="Test PR",
        body_file=body_file,
        base="main",
        remote="origin",
        draft=False,
        restore_branch=True,
        allow_dirty=False,
        allow_detached=False,
        allow_base_branch=False,
    )

    current_branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    assert report["status"] == "ok"
    assert report["restored_state"] is True
    assert current_branch == original_branch


def test_pr_open_restores_branch_after_failure(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo_with_origin(tmp_path)
    body_file = tmp_path / "PR_BODY_FAIL.md"
    body_file.write_text("PR body\n", encoding="utf-8")

    original_branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)

    monkeypatch.setattr("taskx.pr.open.shutil.which", lambda _name: None)

    switched = {"done": False}

    def _failing_run(cmd: list[str], *, cwd: Path):  # type: ignore[no-untyped-def]
        if cmd[:3] == ["git", "push", "-u"] and not switched["done"]:
            switched["done"] = True
            _run(["git", "checkout", "main"], cwd=cwd)
            raise RuntimeError("forced push failure")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("taskx.pr.open._run", _failing_run)

    with pytest.raises(RuntimeError, match="forced push failure"):
        run_pr_open(
            repo_root=repo,
            title="Test PR",
            body_file=body_file,
            base="main",
            remote="origin",
            draft=False,
            restore_branch=True,
            allow_dirty=False,
            allow_detached=False,
            allow_base_branch=False,
        )

    current_branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    assert current_branch == original_branch
