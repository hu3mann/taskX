"""Tests for commit sequencing from task packet commit plans."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from taskx.git.commit_sequence import commit_sequence
from taskx.git.worktree import start_worktree
from taskx.obs.run_artifacts import COMMIT_SEQUENCE_RUN_FILENAME, WORKTREE_FILENAME


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


def _write_allowlist_diff(run_dir: Path) -> None:
    payload = {
        "schema_version": "1.0",
        "violations": {"count": 0, "items": []},
    }
    (run_dir / "ALLOWLIST_DIFF.json").write_text(
        f"{json.dumps(payload, indent=2)}\n",
        encoding="utf-8",
    )


def _write_promotion(run_dir: Path) -> None:
    (run_dir / "PROMOTION_TOKEN.json").write_text(
        '{"status":"passed","token":"abc"}\n',
        encoding="utf-8",
    )


def _write_task_packet(run_dir: Path, *, commit_plan: dict[str, object]) -> None:
    (run_dir / "TASK_PACKET.md").write_text(
        f"""# TASK_PACKET TP_0110 — Commit Sequence Test

## GOAL
Validate commit sequencing.

## SCOPE (ALLOWLIST)
- src/a.txt
- src/b.txt
- README.md

## NON-NEGOTIABLES
- test

## REQUIRED CHANGES
- test

## COMMIT PLAN
```json
{json.dumps(commit_plan, indent=2)}
```

## VERIFICATION COMMANDS
```bash
git status --short
```

## DEFINITION OF DONE
- test

## SOURCES
- src/a.txt
""",
        encoding="utf-8",
    )


def _load_worktree_path(run_dir: Path) -> Path:
    payload = json.loads((run_dir / WORKTREE_FILENAME).read_text(encoding="utf-8"))
    return Path(payload["worktree_path"]).resolve()


def test_commit_sequence_creates_commit_stack_from_plan(repo_with_origin: Path) -> None:
    repo = repo_with_origin
    run_dir = repo / "out" / "runs" / "RUN_SEQ_PASS"
    run_dir.mkdir(parents=True)
    _write_allowlist_diff(run_dir)
    _write_promotion(run_dir)
    _write_task_packet(
        run_dir,
        commit_plan={
            "commit_plan": [
                {
                    "step_id": "C1",
                    "message": "first step",
                    "allowlist": ["src/a.txt"],
                    "verify": ["git status --short"],
                },
                {
                    "step_id": "C2",
                    "message": "second step",
                    "allowlist": ["src/b.txt"],
                    "verify": ["git status --short"],
                },
            ]
        },
    )

    start_report = start_worktree(
        run_dir=run_dir,
        repo_root=repo,
        branch="taskx/run-seq-pass",
        worktree_path=repo / "out" / "worktrees" / "RUN_SEQ_PASS",
        dirty_policy="refuse",
    )
    assert start_report["status"] == "passed"

    worktree = _load_worktree_path(run_dir)
    (worktree / "src").mkdir(parents=True, exist_ok=True)
    (worktree / "src" / "a.txt").write_text("a1\n", encoding="utf-8")
    (worktree / "src" / "b.txt").write_text("b1\n", encoding="utf-8")

    report = commit_sequence(run_dir=run_dir, dirty_policy="refuse")

    assert report["status"] == "passed"
    assert len(report["steps"]) == 2
    assert all(step["status"] == "passed" for step in report["steps"])
    assert (run_dir / COMMIT_SEQUENCE_RUN_FILENAME).exists()

    messages = _git(worktree, "log", "--pretty=%s", "-n", "2").splitlines()
    assert messages[0] == "TP_0110 C2: second step"
    assert messages[1] == "TP_0110 C1: first step"


def test_commit_sequence_refuses_on_main_branch(repo_with_origin: Path) -> None:
    repo = repo_with_origin
    run_dir = repo / "out" / "runs" / "RUN_SEQ_MAIN"
    run_dir.mkdir(parents=True)
    _write_allowlist_diff(run_dir)
    _write_promotion(run_dir)
    _write_task_packet(
        run_dir,
        commit_plan={
            "commit_plan": [
                {
                    "step_id": "C1",
                    "message": "touch readme",
                    "allowlist": ["README.md"],
                }
            ]
        },
    )

    (repo / WORKTREE_FILENAME).write_text("{}", encoding="utf-8")
    (run_dir / WORKTREE_FILENAME).write_text(
        json.dumps(
            {
                "repo_root": str(repo.resolve()),
                "worktree_path": str(repo.resolve()),
                "branch": "main",
                "base_branch": "main",
                "remote": "origin",
            }
        ),
        encoding="utf-8",
    )
    (repo / "README.md").write_text("changed\n", encoding="utf-8")

    report = commit_sequence(run_dir=run_dir)

    assert report["status"] == "failed"
    assert any("main branch" in error for error in report["errors"])


def test_commit_sequence_refuses_when_index_already_staged(repo_with_origin: Path) -> None:
    repo = repo_with_origin
    run_dir = repo / "out" / "runs" / "RUN_SEQ_STAGED"
    run_dir.mkdir(parents=True)
    _write_allowlist_diff(run_dir)
    _write_promotion(run_dir)
    _write_task_packet(
        run_dir,
        commit_plan={
            "commit_plan": [
                {
                    "step_id": "C1",
                    "message": "stage a",
                    "allowlist": ["src/a.txt"],
                }
            ]
        },
    )

    start_report = start_worktree(
        run_dir=run_dir,
        repo_root=repo,
        branch="taskx/run-seq-staged",
        worktree_path=repo / "out" / "worktrees" / "RUN_SEQ_STAGED",
        dirty_policy="refuse",
    )
    assert start_report["status"] == "passed"

    worktree = _load_worktree_path(run_dir)
    (worktree / "src").mkdir(parents=True, exist_ok=True)
    (worktree / "src" / "a.txt").write_text("staged\n", encoding="utf-8")
    _git(worktree, "add", "src/a.txt")

    report = commit_sequence(run_dir=run_dir)

    assert report["status"] == "failed"
    assert any("pre-staged" in error for error in report["errors"])


def test_commit_sequence_refuses_empty_step(repo_with_origin: Path) -> None:
    repo = repo_with_origin
    run_dir = repo / "out" / "runs" / "RUN_SEQ_EMPTY"
    run_dir.mkdir(parents=True)
    _write_allowlist_diff(run_dir)
    _write_promotion(run_dir)
    _write_task_packet(
        run_dir,
        commit_plan={
            "commit_plan": [
                {
                    "step_id": "C1",
                    "message": "no changes",
                    "allowlist": ["src/missing.txt"],
                }
            ]
        },
    )

    start_report = start_worktree(
        run_dir=run_dir,
        repo_root=repo,
        branch="taskx/run-seq-empty",
        worktree_path=repo / "out" / "worktrees" / "RUN_SEQ_EMPTY",
        dirty_policy="refuse",
    )
    assert start_report["status"] == "passed"

    report = commit_sequence(run_dir=run_dir)

    assert report["status"] == "failed"
    assert any("empty commit" in error for error in report["errors"])
