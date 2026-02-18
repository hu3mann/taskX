"""Tests for taskx neon CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from taskx.cli import cli
from taskx.ui import THEMES

runner = CliRunner()


# neon list tests


def test_neon_list_shows_all_themes(monkeypatch) -> None:
    """neon list displays all available themes."""
    monkeypatch.setenv("TASKX_NEON", "1")

    result = runner.invoke(cli, ["neon", "list"])
    assert result.exit_code == 0

    for theme_name in THEMES:
        assert theme_name in result.output


def test_neon_list_works_with_neon_disabled(monkeypatch) -> None:
    """neon list works even when TASKX_NEON=0."""
    monkeypatch.setenv("TASKX_NEON", "0")

    result = runner.invoke(cli, ["neon", "list"])
    assert result.exit_code == 0

    for theme_name in THEMES:
        assert theme_name in result.output


# neon preview tests


def test_neon_preview_valid_theme(monkeypatch) -> None:
    """neon preview displays banner for valid theme."""
    monkeypatch.setenv("TASKX_NEON", "1")

    result = runner.invoke(cli, ["neon", "preview", "cyberpunk"])
    assert result.exit_code == 0
    assert "DETERMINISTIC TASK EXECUTION KERNEL" in result.output
    assert "Theme: cyberpunk" in result.output


def test_neon_preview_invalid_theme_neon_enabled(monkeypatch) -> None:
    """neon preview exits with error for unknown theme (neon on)."""
    monkeypatch.setenv("TASKX_NEON", "1")

    result = runner.invoke(cli, ["neon", "preview", "nonexistent"])
    assert result.exit_code == 2
    assert "Unknown theme" in result.output or "unknown theme" in result.output.lower()
    assert "taskx neon list" in result.output


def test_neon_preview_invalid_theme_neon_disabled(monkeypatch) -> None:
    """neon preview exits with error for unknown theme (neon off)."""
    monkeypatch.setenv("TASKX_NEON", "0")

    result = runner.invoke(cli, ["neon", "preview", "nonexistent"])
    assert result.exit_code == 2
    assert "Unknown theme" in result.output
    assert "taskx neon list" in result.output


# neon demo tests


def test_neon_demo_cycles_themes(monkeypatch) -> None:
    """neon demo shows all themes in sequence."""
    monkeypatch.setenv("TASKX_NEON", "1")

    result = runner.invoke(cli, ["neon", "demo", "--delay-ms", "0"])
    assert result.exit_code == 0

    # All themes should appear in output
    for theme_name in THEMES:
        assert f"Theme: {theme_name}" in result.output


def test_neon_demo_accepts_custom_delay(monkeypatch) -> None:
    """neon demo accepts custom delay parameter."""
    monkeypatch.setenv("TASKX_NEON", "1")

    result = runner.invoke(cli, ["neon", "demo", "--delay-ms", "1"])
    assert result.exit_code == 0


# neon set tests


def test_neon_set_valid_theme_neon_enabled(monkeypatch) -> None:
    """neon set prints export line for valid theme (neon on)."""
    monkeypatch.setenv("TASKX_NEON", "1")

    result = runner.invoke(cli, ["neon", "set", "ultraviolet"])
    assert result.exit_code == 0
    assert 'export TASKX_THEME="ultraviolet"' in result.output
    assert "Copy/paste into your shell" in result.output or "copy" in result.output.lower()


def test_neon_set_valid_theme_neon_disabled(monkeypatch) -> None:
    """neon set prints export line for valid theme (neon off)."""
    monkeypatch.setenv("TASKX_NEON", "0")

    result = runner.invoke(cli, ["neon", "set", "toxic_lime"])
    assert result.exit_code == 0
    assert 'export TASKX_THEME="toxic_lime"' in result.output


def test_neon_set_invalid_theme_neon_enabled(monkeypatch) -> None:
    """neon set exits with error for unknown theme (neon on)."""
    monkeypatch.setenv("TASKX_NEON", "1")

    result = runner.invoke(cli, ["neon", "set", "invalid_theme"])
    assert result.exit_code == 2
    assert "Unknown theme" in result.output or "unknown theme" in result.output.lower()


def test_neon_set_invalid_theme_neon_disabled(monkeypatch) -> None:
    """neon set exits with error for unknown theme (neon off)."""
    monkeypatch.setenv("TASKX_NEON", "0")

    result = runner.invoke(cli, ["neon", "set", "bad_theme"])
    assert result.exit_code == 2
    assert "Unknown theme" in result.output


# neon status tests


def test_neon_status_shows_all_settings_neon_enabled(monkeypatch) -> None:
    """neon status displays all environment settings (neon on)."""
    monkeypatch.setenv("TASKX_NEON", "1")
    monkeypatch.setenv("TASKX_STRICT", "1")
    monkeypatch.setenv("TASKX_THEME", "magma")

    result = runner.invoke(cli, ["neon", "status"])
    assert result.exit_code == 0
    assert "TASKX_NEON=1" in result.output
    assert "TASKX_STRICT=1" in result.output
    assert "TASKX_THEME=magma" in result.output


def test_neon_status_shows_defaults(monkeypatch) -> None:
    """neon status shows default values when env vars not set."""
    monkeypatch.delenv("TASKX_NEON", raising=False)
    monkeypatch.delenv("TASKX_STRICT", raising=False)
    monkeypatch.delenv("TASKX_THEME", raising=False)

    result = runner.invoke(cli, ["neon", "status"])
    assert result.exit_code == 0
    assert "TASKX_NEON=1" in result.output  # default is on
    assert "TASKX_STRICT=0" in result.output  # default is off
    assert "TASKX_THEME=mintwave" in result.output  # default theme


def test_neon_status_works_with_neon_disabled(monkeypatch) -> None:
    """neon status works when TASKX_NEON=0."""
    monkeypatch.setenv("TASKX_NEON", "0")
    monkeypatch.setenv("TASKX_STRICT", "0")
    monkeypatch.setenv("TASKX_THEME", "cyberpunk")

    result = runner.invoke(cli, ["neon", "status"])
    assert result.exit_code == 0
    assert "TASKX_NEON=0" in result.output
    assert "TASKX_STRICT=0" in result.output
    assert "TASKX_THEME=cyberpunk" in result.output


# neon persist tests


def test_neon_persist_invalid_shell_neon_enabled(monkeypatch, tmp_path) -> None:
    """neon persist exits with error for invalid --shell value (neon on)."""
    monkeypatch.setenv("TASKX_NEON", "1")
    rc_file = tmp_path / "testrc"
    rc_file.touch()

    result = runner.invoke(cli, ["neon", "persist", "--shell", "fish", "--rc-path", str(rc_file)])
    assert result.exit_code == 2
    assert "invalid shell" in result.output
    assert "fish" in result.output
    assert "Valid options: zsh, bash" in result.output


def test_neon_persist_invalid_shell_neon_disabled(monkeypatch, tmp_path) -> None:
    """neon persist exits with error for invalid --shell value (neon off)."""
    monkeypatch.setenv("TASKX_NEON", "0")
    rc_file = tmp_path / "testrc"
    rc_file.touch()

    result = runner.invoke(cli, ["neon", "persist", "--shell", "ksh", "--rc-path", str(rc_file)])
    assert result.exit_code == 2
    assert "invalid shell" in result.output
    assert "ksh" in result.output
    assert "Valid options: zsh, bash" in result.output


def test_neon_persist_valid_shell_zsh(monkeypatch, tmp_path) -> None:
    """neon persist accepts --shell zsh."""
    monkeypatch.setenv("TASKX_NEON", "1")
    rc_file = tmp_path / "testrc"
    rc_file.touch()

    result = runner.invoke(cli, ["neon", "persist", "--shell", "zsh", "--rc-path", str(rc_file)])
    assert result.exit_code == 0


def test_neon_persist_valid_shell_bash(monkeypatch, tmp_path) -> None:
    """neon persist accepts --shell bash."""
    monkeypatch.setenv("TASKX_NEON", "1")
    rc_file = tmp_path / "testrc"
    rc_file.touch()

    result = runner.invoke(cli, ["neon", "persist", "--shell", "bash", "--rc-path", str(rc_file)])
    assert result.exit_code == 0
