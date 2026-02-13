"""Integration-style tests for dirty-policy stash behavior and finish divergence."""

from __future__ import annotations

import json
import pathlib
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from taskx.cli import cli

if TYPE_CHECKING:
    from pathlib import Path


def _run(cmd: list[str], *, cwd: Path) -> str:
    """Run command and return stdout."""
    result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _init_repo_with_origin(tmp_path: Path) -> tuple[Path, Path]:
    """Create a repo clone with origin/main and baseline tracked file."""
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
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "file.py").write_text("print('base')\n", encoding="utf-8")
    _run(["git", "add", "README.md", "src/file.py"], cwd=repo)
    _run(["git", "commit", "-m", "init"], cwd=repo)
    _run(["git", "push", "-u", "origin", "main"], cwd=repo)
    return repo, remote


def _write_task_packet(run_dir: Path) -> None:
    """Write Task Packet with one-step COMMIT PLAN."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "TASK_PACKET.md").write_text(
        """# TASK_PACKET TP_0001 — Demo

## COMMIT PLAN
```json
{
  "commit_plan": [
    {
      "step_id": "C1",
      "message": "feat: update file",
      "allowlist": ["src/file.py"],
      "verify": []
    }
  ]
}
```
""",
        encoding="utf-8",
    )


def _load_worktree_json(run_dir: Path) -> dict:
    return json.loads((run_dir / "WORKTREE.json").read_text(encoding="utf-8"))


def _load_dirty_state(run_dir: Path) -> list[dict]:
    payload = json.loads((run_dir / "DIRTY_STATE.json").read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return payload


def test_wt_start_stash_logs_repo_root_dirt(tmp_path: Path, monkeypatch) -> None:
    """wt start should stash root dirt and write DIRTY_STATE entry."""
    repo, _ = _init_repo_with_origin(tmp_path)
    run_dir = tmp_path / "RUN_0101"

    # Dirty root: tracked + untracked.
    (repo / "README.md").write_text("# dirty\n", encoding="utf-8")
    (repo / "notes.txt").write_text("todo\n", encoding="utf-8")

    runner = CliRunner()
    monkeypatch.chdir(repo)
    result = runner.invoke(
        cli,
        [
            "wt",
            "start",
            "--run",
            str(run_dir),
            "--branch",
            "tp/taskx.core/0101-feature",
            "--dirty-policy",
            "stash",
        ],
    )
    assert result.exit_code == 0

    worktree = _load_worktree_json(run_dir)
    assert Path(worktree["worktree_path"]).exists()
    dirty_state = _load_dirty_state(run_dir)
    assert len(dirty_state) == 1
    entry = dirty_state[0]
    assert entry["location"] == "repo_root"
    assert entry["policy"] == "stash"
    assert entry["stash_ref"]
    assert entry["status_porcelain"] == sorted(entry["status_porcelain"])
    assert any("README.md" in line for line in entry["status_porcelain"])
    assert any("notes.txt" in line for line in entry["status_porcelain"])
    assert worktree["branch"] == "tp/taskx.core/0101-feature"


def test_commit_sequence_stash_only_disallowed_changes(tmp_path: Path, monkeypatch) -> None:
    """commit-sequence should stash out-of-allowlist dirt while committing allowlisted changes."""
    repo, _ = _init_repo_with_origin(tmp_path)
    run_dir = tmp_path / "RUN_0102"
    _write_task_packet(run_dir)

    runner = CliRunner()
    monkeypatch.chdir(repo)
    start = runner.invoke(
        cli,
        ["wt", "start", "--run", str(run_dir), "--branch", "tp/0102-feature"],
    )
    assert start.exit_code == 0

    worktree_path = subprocess.check_output(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo,
        text=True,
    )
    assert "tp_0102_feature" in worktree_path
    wt = repo / "out" / "worktrees" / "tp_0102_feature"

    (wt / "src" / "file.py").write_text("print('allowlisted')\n", encoding="utf-8")
    (wt / "wip.txt").write_text("scratch\n", encoding="utf-8")

    monkeypatch.chdir(wt)
    run = runner.invoke(
        cli,
        [
            "commit-sequence",
            "--run",
            str(run_dir),
            "--allow-unpromoted",
            "--dirty-policy",
            "stash",
        ],
    )
    assert run.exit_code == 0

    changed = _run(["git", "show", "--name-only", "--pretty=format:", "HEAD"], cwd=wt)
    assert "src/file.py" in changed.splitlines()
    assert "wip.txt" not in changed.splitlines()

    dirty_state = _load_dirty_state(run_dir)
    assert len(dirty_state) == 1
    entry = dirty_state[0]
    assert entry["location"] == "worktree"
    assert entry["policy"] == "stash"
    assert entry["stash_ref"]
    assert any("wip.txt" in line for line in entry["status_porcelain"])


def test_finish_stash_cleans_up_and_appends_dirty_state(tmp_path: Path, monkeypatch) -> None:
    """finish with stash should stash dirty worktree and remove worktree/branch by default."""
    repo, _ = _init_repo_with_origin(tmp_path)
    run_dir = tmp_path / "RUN_0103"
    _write_task_packet(run_dir)

    runner = CliRunner()
    monkeypatch.chdir(repo)
    assert runner.invoke(cli, ["wt", "start", "--run", str(run_dir), "--branch", "tp/0103-feature"]).exit_code == 0

    wt = repo / "out" / "worktrees" / "tp_0103_feature"
    (wt / "src" / "file.py").write_text("print('commit me')\n", encoding="utf-8")
    monkeypatch.chdir(wt)
    assert (
        runner.invoke(
            cli,
            ["commit-sequence", "--run", str(run_dir), "--allow-unpromoted"],
        ).exit_code
        == 0
    )

    # Dirty before finish so stash path is exercised.
    (wt / "temp_untracked.txt").write_text("dirty\n", encoding="utf-8")
    finish = runner.invoke(cli, ["finish", "--run", str(run_dir), "--dirty-policy", "stash"])
    assert finish.exit_code == 0

    dirty_state = _load_dirty_state(run_dir)
    assert len(dirty_state) == 1
    assert dirty_state[0]["location"] == "worktree"
    assert dirty_state[0]["policy"] == "stash"

    worktree_meta = _load_worktree_json(run_dir)
    branch = worktree_meta["branch"]
    assert not pathlib.Path(worktree_meta["worktree_path"]).exists()
    assert _run(["git", "branch", "--list", branch], cwd=repo) == ""
    assert (run_dir / "FINISH.json").exists()


def test_dirty_state_is_append_only_across_stash_phases(tmp_path: Path, monkeypatch) -> None:
    """DIRTY_STATE should append entries and preserve existing records unchanged."""
    repo, _ = _init_repo_with_origin(tmp_path)
    run_dir = tmp_path / "RUN_0104"
    _write_task_packet(run_dir)

    # Phase 1: stash at wt start (repo root dirt).
    (repo / "README.md").write_text("# dirty root\n", encoding="utf-8")
    runner = CliRunner()
    monkeypatch.chdir(repo)
    assert (
        runner.invoke(
            cli,
            ["wt", "start", "--run", str(run_dir), "--branch", "tp/0104-feature", "--dirty-policy", "stash"],
        ).exit_code
        == 0
    )

    entries_before = _load_dirty_state(run_dir)
    assert len(entries_before) == 1
    preserved = json.dumps(entries_before[0], sort_keys=True)

    # Phase 2: stash at finish (worktree dirt).
    wt = repo / "out" / "worktrees" / "tp_0104_feature"
    (wt / "scratch.txt").write_text("dirty worktree\n", encoding="utf-8")
    monkeypatch.chdir(wt)
    assert (
        runner.invoke(
            cli,
            ["finish", "--run", str(run_dir), "--dirty-policy", "stash", "--no-cleanup"],
        ).exit_code
        == 0
    )

    entries_after = _load_dirty_state(run_dir)
    assert len(entries_after) == 2
    assert json.dumps(entries_after[0], sort_keys=True) == preserved
    assert entries_after[1]["location"] == "worktree"
    assert entries_after[1]["policy"] == "stash"


def test_finish_refuses_when_main_not_fast_forwardable(tmp_path: Path, monkeypatch) -> None:
    """finish should refuse when local main diverged and cannot ff-only to origin/main."""
    repo, remote = _init_repo_with_origin(tmp_path)
    run_dir = tmp_path / "RUN_0105"
    _write_task_packet(run_dir)

    runner = CliRunner()
    monkeypatch.chdir(repo)
    assert runner.invoke(cli, ["wt", "start", "--run", str(run_dir), "--branch", "tp/0105-feature"]).exit_code == 0

    wt = repo / "out" / "worktrees" / "tp_0105_feature"
    (wt / "src" / "file.py").write_text("print('branch change')\n", encoding="utf-8")
    monkeypatch.chdir(wt)
    assert (
        runner.invoke(
            cli,
            ["commit-sequence", "--run", str(run_dir), "--allow-unpromoted"],
        ).exit_code
        == 0
    )

    # Advance origin/main in a second clone.
    second = tmp_path / "second"
    subprocess.run(["git", "clone", str(remote), str(second)], check=True, capture_output=True)
    _run(["git", "checkout", "-B", "main", "origin/main"], cwd=second)
    _run(["git", "config", "user.email", "test@example.com"], cwd=second)
    _run(["git", "config", "user.name", "Other User"], cwd=second)
    (second / "remote_only.txt").write_text("remote move\n", encoding="utf-8")
    _run(["git", "add", "remote_only.txt"], cwd=second)
    _run(["git", "commit", "-m", "remote advance"], cwd=second)
    _run(["git", "push", "-u", "origin", "main"], cwd=second)

    # Diverge local main so ff-only sync to origin/main fails.
    monkeypatch.chdir(repo)
    (repo / "local_only.txt").write_text("local diverge\n", encoding="utf-8")
    _run(["git", "add", "local_only.txt"], cwd=repo)
    _run(["git", "commit", "-m", "local diverge"], cwd=repo)

    monkeypatch.chdir(wt)
    finish = runner.invoke(cli, ["finish", "--run", str(run_dir), "--no-cleanup"])
    assert finish.exit_code == 1
    assert "ERROR: main is not fast-forwardable." in finish.stdout
    assert "Repository state diverged." in finish.stdout
