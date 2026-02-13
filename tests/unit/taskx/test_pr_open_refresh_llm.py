"""refresh-llm integration tests for PR open flow."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

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

    _run(["git", "checkout", "-b", "codex/tp-pr-open-branch-guard/feature/refresh"], cwd=repo)
    (repo / "feature.txt").write_text("change\n", encoding="utf-8")
    _run(["git", "add", "feature.txt"], cwd=repo)
    _run(["git", "commit", "-m", "feature"], cwd=repo)
    return repo


def test_pr_open_runs_refresh_llm_when_enabled(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo_with_origin(tmp_path)
    body_file = tmp_path / "PR_BODY.md"
    body_file.write_text("PR body\n", encoding="utf-8")

    monkeypatch.setattr("taskx.pr.open.shutil.which", lambda _name: None)

    original_git_output = pr_open_module._git_output

    def _patched_git_output(repo_root: Path, args: list[str]) -> str:
        if args == ["remote", "get-url", "origin"]:
            return "https://github.com/acme/taskX.git"
        return original_git_output(repo_root, args)

    monkeypatch.setattr("taskx.pr.open._git_output", _patched_git_output)

    called = {"count": 0}

    def _refresh_runner(_repo_root: Path) -> dict[str, object]:
        called["count"] += 1
        return {"status": "ok"}

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
        require_branch_prefix="codex/tp-pr-open-branch-guard",
        allow_branch_prefix_override=False,
        refresh_llm=True,
        refresh_llm_runner=_refresh_runner,
    )

    assert report["status"] == "ok"
    assert report["llm_refresh"]["ran"] is True
    assert report["llm_refresh"]["status"] == "ok"
    assert called["count"] == 1
