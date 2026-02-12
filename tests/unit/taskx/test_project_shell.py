"""Tests for project shell init/status and doctor direnv warning."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from taskx.cli import cli
from taskx.doctor import run_doctor
from taskx.project.shell import init_shell, status_shell

if TYPE_CHECKING:
    from pathlib import Path

RUNNER = CliRunner()

EXPECTED_ENVRC = 'export PATH="$(pwd)/scripts:$PATH"\n'
EXPECTED_TASKX_SHIM = (
    "#!/usr/bin/env bash\n"
    "set -euo pipefail\n"
    "exec \"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)/taskx-local\" \"$@\"\n"
)
EXPECTED_TASKX_LOCAL = (
    "#!/usr/bin/env bash\n"
    "set -euo pipefail\n"
    "\n"
    "SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
    "REPO_ROOT=\"$(cd \"$SCRIPT_DIR/..\" && pwd)\"\n"
    "LOCAL_TASKX=\"$REPO_ROOT/.venv-taskx/bin/taskx\"\n"
    "\n"
    "if [[ -x \"$LOCAL_TASKX\" ]]; then\n"
    "  exec \"$LOCAL_TASKX\" \"$@\"\n"
    "fi\n"
    "\n"
    "echo \"WARNING: repo-local TaskX not found at $LOCAL_TASKX; falling back to taskx on PATH\" >&2\n"
    "\n"
    "PATH_NO_LOCAL=\"\"\n"
    "IFS=':' read -r -a PATH_PARTS <<< \"$PATH\"\n"
    "for PART in \"${PATH_PARTS[@]}\"; do\n"
    "  if [[ \"$PART\" == \"$SCRIPT_DIR\" ]]; then\n"
    "    continue\n"
    "  fi\n"
    "  if [[ -z \"$PATH_NO_LOCAL\" ]]; then\n"
    "    PATH_NO_LOCAL=\"$PART\"\n"
    "  else\n"
    "    PATH_NO_LOCAL=\"$PATH_NO_LOCAL:$PART\"\n"
    "  fi\n"
    "done\n"
    "\n"
    "GLOBAL_TASKX=\"$(PATH=\"$PATH_NO_LOCAL\" command -v taskx || true)\"\n"
    "if [[ -n \"$GLOBAL_TASKX\" ]]; then\n"
    "  exec \"$GLOBAL_TASKX\" \"$@\"\n"
    "fi\n"
    "\n"
    "echo \"ERROR: could not find TaskX executable. Create .venv-taskx/bin/taskx or install taskx on PATH.\" >&2\n"
    "exit 2\n"
)


def test_shell_init_creates_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"

    report = init_shell(repo_root)

    assert report["created_files"] == [
        ".envrc",
        "scripts/taskx",
        "scripts/taskx-local",
    ]
    assert report["skipped_files"] == []

    envrc_path = repo_root / ".envrc"
    shim_path = repo_root / "scripts" / "taskx"
    local_path = repo_root / "scripts" / "taskx-local"

    assert envrc_path.read_text(encoding="utf-8") == EXPECTED_ENVRC
    assert shim_path.read_text(encoding="utf-8") == EXPECTED_TASKX_SHIM
    assert local_path.read_text(encoding="utf-8") == EXPECTED_TASKX_LOCAL

    assert shim_path.exists() and local_path.exists()

    json_report_path = repo_root / "out" / "taskx_project_shell" / "PROJECT_SHELL_REPORT.json"
    md_report_path = repo_root / "out" / "taskx_project_shell" / "PROJECT_SHELL_REPORT.md"
    assert json_report_path.exists()
    assert md_report_path.exists()

    payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    assert payload["repo_root"] == str(repo_root.resolve())
    assert payload["created_files"] == [
        ".envrc",
        "scripts/taskx",
        "scripts/taskx-local",
    ]


def test_shell_init_is_idempotent(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    init_shell(repo_root)

    files = [
        repo_root / ".envrc",
        repo_root / "scripts" / "taskx",
        repo_root / "scripts" / "taskx-local",
    ]
    before_snapshot = {str(path): path.read_text(encoding="utf-8") for path in files}
    before_mtimes = {str(path): path.stat().st_mtime_ns for path in files}

    second = init_shell(repo_root)

    assert second["created_files"] == []
    assert second["skipped_files"] == [
        ".envrc",
        "scripts/taskx",
        "scripts/taskx-local",
    ]

    after_snapshot = {str(path): path.read_text(encoding="utf-8") for path in files}
    after_mtimes = {str(path): path.stat().st_mtime_ns for path in files}

    assert after_snapshot == before_snapshot
    assert after_mtimes == before_mtimes


def test_shell_status_reports_presence(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"

    before = status_shell(repo_root)
    assert [file_state["exists"] for file_state in before["files"]] == [False, False, False]

    init_shell(repo_root)

    after = status_shell(repo_root)
    assert [file_state["exists"] for file_state in after["files"]] == [True, True, True]
    assert all(file_state["valid"] for file_state in after["files"])

    cli_result = RUNNER.invoke(
        cli,
        ["project", "shell", "status", "--repo-root", str(repo_root)],
    )
    assert cli_result.exit_code == 0, cli_result.output
    assert "Repo:" in cli_result.output
    assert "Direnv found:" in cli_result.output


def test_doctor_warns_when_envrc_present_direnv_missing(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / ".envrc").write_text(EXPECTED_ENVRC, encoding="utf-8")

    def _fake_which(binary: str) -> str | None:
        if binary == "direnv":
            return None
        if binary == "git":
            return "/usr/bin/git"
        return None

    monkeypatch.setattr("taskx.doctor.shutil.which", _fake_which)

    report = run_doctor(
        out_dir=tmp_path / "doctor_out",
        timestamp_mode="deterministic",
        require_git=False,
        repo_root=repo_root,
    )

    items = {item["id"]: item for item in report.checks["items"]}
    assert report.status == "passed"
    assert items["direnv_envrc"]["status"] == "warn"
    assert "direnv is not installed" in items["direnv_envrc"]["message"]
