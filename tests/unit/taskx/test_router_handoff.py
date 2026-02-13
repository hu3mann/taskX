"""Handoff output coverage for TaskX route artifacts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from taskx.cli import cli

if TYPE_CHECKING:
    from pathlib import Path


def test_route_handoff_contains_runner_sections(tmp_path: Path, monkeypatch) -> None:
    """Handoff markdown should include all expected runner prompt/command sections."""
    runner = CliRunner()
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    packet = repo / "PACKET.md"
    packet.write_text("# Packet\n", encoding="utf-8")

    monkeypatch.chdir(repo)

    init_result = runner.invoke(cli, ["route", "init", "--repo-root", str(repo)])
    assert init_result.exit_code == 0, init_result.output

    handoff_result = runner.invoke(
        cli,
        ["route", "handoff", "--repo-root", str(repo), "--packet", str(packet)],
    )
    assert handoff_result.exit_code == 0, handoff_result.output

    handoff_path = repo / "out" / "taskx_route" / "HANDOFF.md"
    contents = handoff_path.read_text(encoding="utf-8")

    assert "Codex Desktop prompt" in contents
    assert "Claude Code prompt" in contents
    assert "Copilot CLI command" in contents
