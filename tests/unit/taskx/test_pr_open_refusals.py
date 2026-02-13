"""Refusal tests for PR open CLI flow."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from taskx.cli import cli

if TYPE_CHECKING:
    from pathlib import Path


def _run(cmd: list[str], *, cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "Test User"], cwd=repo)
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    _run(["git", "add", "README.md"], cwd=repo)
    _run(["git", "commit", "-m", "init"], cwd=repo)
    return repo


def test_pr_open_refuses_dirty_tree(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    body_file = tmp_path / "PR_BODY.md"
    body_file.write_text("PR body\n", encoding="utf-8")
    (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    runner = CliRunner()
    monkeypatch.chdir(repo)
    result = runner.invoke(
        cli,
        [
            "pr",
            "open",
            "--repo-root",
            str(repo),
            "--title",
            "Test PR",
            "--body-file",
            str(body_file),
        ],
    )

    assert result.exit_code == 2
    payload = json.loads((repo / "out" / "taskx_pr" / "PR_OPEN_REPORT.json").read_text(encoding="utf-8"))
    assert payload["status"] == "refused"
    assert "dirty" in payload["refusal_reason"].lower()


def test_pr_open_refuses_detached_head(tmp_path: Path, monkeypatch) -> None:
    repo = _init_repo(tmp_path)
    body_file = tmp_path / "PR_BODY_DETACHED.md"
    body_file.write_text("PR body\n", encoding="utf-8")

    _run(["git", "checkout", "--detach", "HEAD"], cwd=repo)

    runner = CliRunner()
    monkeypatch.chdir(repo)
    result = runner.invoke(
        cli,
        [
            "pr",
            "open",
            "--repo-root",
            str(repo),
            "--title",
            "Test PR",
            "--body-file",
            str(body_file),
        ],
    )

    assert result.exit_code == 2
    payload = json.loads((repo / "out" / "taskx_pr" / "PR_OPEN_REPORT.json").read_text(encoding="utf-8"))
    assert payload["status"] == "refused"
    assert "detached" in payload["refusal_reason"].lower()
