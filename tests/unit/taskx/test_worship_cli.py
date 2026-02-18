"""Tests for taskx worship easter egg command."""

from __future__ import annotations

from typer.testing import CliRunner

from taskx.cli import cli

runner = CliRunner()


def test_worship_command_neon_enabled(monkeypatch) -> None:
    """worship command outputs formatted text when TASKX_NEON=1."""
    monkeypatch.setenv("TASKX_NEON", "1")

    result = runner.invoke(cli, ["worship"])
    assert result.exit_code == 0

    # Check all expected lines appear
    assert "KERNEL WORSHIP ACCEPTED" in result.output
    assert "Show me the packet." in result.output
    assert "Leave artifacts. No excuses." in result.output
    assert "One path. Stay honest." in result.output
    assert "Refusal is integrity." in result.output


def test_worship_command_neon_disabled(monkeypatch) -> None:
    """worship command outputs plain text when TASKX_NEON=0."""
    monkeypatch.setenv("TASKX_NEON", "0")

    result = runner.invoke(cli, ["worship"])
    assert result.exit_code == 0

    # Check all expected lines appear in plain mode
    assert "KERNEL WORSHIP ACCEPTED" in result.output
    assert "Show me the packet." in result.output
    assert "Leave artifacts. No excuses." in result.output
    assert "One path. Stay honest." in result.output
    assert "Refusal is integrity." in result.output


def test_worship_command_is_reproducible(monkeypatch) -> None:
    """worship command produces same output on repeated calls."""
    monkeypatch.setenv("TASKX_NEON", "1")

    result1 = runner.invoke(cli, ["worship"])
    result2 = runner.invoke(cli, ["worship"])

    assert result1.exit_code == 0
    assert result2.exit_code == 0
    assert result1.output == result2.output
