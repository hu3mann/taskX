"""Tests for project upgrade orchestrator command."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from taskx.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

RUNNER = CliRunner()


def _report_json(repo_root: Path) -> dict:
    report_path = repo_root / "out" / "taskx_project_upgrade" / "PROJECT_UPGRADE_REPORT.json"
    assert report_path.exists()
    return json.loads(report_path.read_text(encoding="utf-8"))


def test_project_upgrade_refuses_when_rails_missing_without_allow_init(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"

    result = RUNNER.invoke(
        cli,
        [
            "project",
            "upgrade",
            "--repo-root",
            str(repo_root),
            "--no-shell",
            "--no-packs",
            "--no-doctor",
        ],
    )

    assert result.exit_code == 2
    assert "Missing identity rails" in result.output
    assert "Refusing to" in result.output


def test_project_upgrade_creates_rails_with_allow_init(tmp_path: Path) -> None:
    repo_root = tmp_path / "repoA"

    result = RUNNER.invoke(
        cli,
        [
            "project",
            "upgrade",
            "--repo-root",
            str(repo_root),
            "--allow-init-rails",
            "--no-shell",
            "--no-packs",
            "--no-doctor",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (repo_root / ".taskxroot").exists()
    project_json = repo_root / ".taskx" / "project.json"
    assert project_json.exists()

    payload = json.loads(project_json.read_text(encoding="utf-8"))
    assert payload["project_id"] == "repoA"

    report = _report_json(repo_root)
    assert report["rails_state"]["status"] == "initialized"
    assert report["rails_state"]["project_id_auto_derived"] is True


def test_project_upgrade_shell_is_idempotent(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"

    first = RUNNER.invoke(
        cli,
        [
            "project",
            "upgrade",
            "--repo-root",
            str(repo_root),
            "--allow-init-rails",
            "--shell",
            "--no-packs",
            "--no-doctor",
        ],
    )
    assert first.exit_code == 0, first.output
    first_report = _report_json(repo_root)
    assert ".envrc" in first_report["shell_init"]["created_files"]

    second = RUNNER.invoke(
        cli,
        [
            "project",
            "upgrade",
            "--repo-root",
            str(repo_root),
            "--allow-init-rails",
            "--shell",
            "--no-packs",
            "--no-doctor",
        ],
    )
    assert second.exit_code == 0, second.output
    second_report = _report_json(repo_root)

    assert second_report["shell_init"]["created_files"] == []
    assert second_report["shell_init"]["skipped_files"] == [
        ".envrc",
        "scripts/taskx",
        "scripts/taskx-local",
    ]


def test_project_upgrade_runs_packs_doctor(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"

    result = RUNNER.invoke(
        cli,
        [
            "project",
            "upgrade",
            "--repo-root",
            str(repo_root),
            "--allow-init-rails",
            "--no-shell",
            "--packs",
            "--no-doctor",
            "--mode",
            "both",
        ],
    )

    assert result.exit_code == 0, result.output

    instructions_root = repo_root / ".taskx" / "instructions"
    for name in ["PROJECT_INSTRUCTIONS.md", "CLAUDE.md", "CODEX.md", "AGENTS.md"]:
        assert (instructions_root / name).exists()

    agents_text = (instructions_root / "AGENTS.md").read_text(encoding="utf-8")
    assert "<!-- TASKX:BEGIN -->" in agents_text
    assert "<!-- CHATX:BEGIN -->" in agents_text

    report = _report_json(repo_root)
    assert report["packs_doctor"]["status"] == "pass"


def test_project_upgrade_doctor_warns_when_direnv_missing(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"

    def _fake_which(binary: str) -> str | None:
        if binary == "direnv":
            return None
        if binary == "git":
            return "/usr/bin/git"
        return None

    monkeypatch.setattr("taskx.project.shell.shutil.which", _fake_which)
    monkeypatch.setattr("taskx.doctor.shutil.which", _fake_which)

    result = RUNNER.invoke(
        cli,
        [
            "project",
            "upgrade",
            "--repo-root",
            str(repo_root),
            "--allow-init-rails",
            "--shell",
            "--no-packs",
            "--doctor",
        ],
    )

    assert result.exit_code == 0, result.output

    report = _report_json(repo_root)
    assert report["doctor"]["status"] == "passed"
    checks_by_id = {item["id"]: item for item in report["doctor"]["checks"]["items"]}
    assert checks_by_id["direnv_envrc"]["status"] == "warn"
    assert "direnv is not installed" in checks_by_id["direnv_envrc"]["message"]

    md_report = repo_root / "out" / "taskx_project_upgrade" / "PROJECT_UPGRADE_REPORT.md"
    assert md_report.exists()
    assert "# PROJECT_UPGRADE_REPORT" in md_report.read_text(encoding="utf-8")
