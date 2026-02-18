from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from taskx.cli import app
from taskx.neon_persist import MARKER_BEGIN, MARKER_END, persist_rc_file, render_block


def test_persist_dry_run_does_not_write(tmp_path: Path) -> None:
    rc = tmp_path / "rc"
    result = persist_rc_file(
        path=rc,
        neon="1",
        theme="mintwave",
        strict="0",
        remove=False,
        dry_run=True,
    )

    assert result.backup_path is None
    assert not rc.exists()
    assert MARKER_BEGIN in result.diff
    assert MARKER_END in result.diff


def test_persist_write_creates_backup_and_is_idempotent(tmp_path: Path) -> None:
    rc = tmp_path / "rc"
    rc.write_text("export FOO=1\n", encoding="utf-8")

    result1 = persist_rc_file(
        path=rc,
        neon="1",
        theme="mintwave",
        strict="0",
        remove=False,
        dry_run=False,
        backup_suffix_fn=lambda: "TEST1",
    )
    assert result1.backup_path is not None
    assert result1.backup_path.exists()
    assert result1.backup_path.read_text(encoding="utf-8") == "export FOO=1\n"
    content1 = rc.read_text(encoding="utf-8")
    assert MARKER_BEGIN in content1

    # Second call with identical settings should not change the file
    result2 = persist_rc_file(
        path=rc,
        neon="1",
        theme="mintwave",
        strict="0",
        remove=False,
        dry_run=False,
        backup_suffix_fn=lambda: "TEST2",
    )
    # No backup is created when the file is unchanged (idempotent behavior)
    assert result2.backup_path is None
    assert not result2.changed
    assert rc.read_text(encoding="utf-8") == content1


def test_remove_deletes_only_managed_block(tmp_path: Path) -> None:
    rc = tmp_path / "rc"
    block = render_block(neon="1", theme="mintwave", strict="0")
    rc.write_text(f"export FOO=1\n{block}export BAR=2\n", encoding="utf-8")

    persist_rc_file(
        path=rc,
        neon="1",
        theme="mintwave",
        strict="0",
        remove=True,
        dry_run=False,
        backup_suffix_fn=lambda: "TEST",
    )
    new = rc.read_text(encoding="utf-8")
    assert "export FOO=1" in new
    assert "export BAR=2" in new
    assert MARKER_BEGIN not in new
    assert MARKER_END not in new


def test_replace_existing_block(tmp_path: Path) -> None:
    rc = tmp_path / "rc"
    old_block = render_block(neon="0", theme="magma", strict="1")
    rc.write_text(old_block, encoding="utf-8")

    persist_rc_file(
        path=rc,
        neon="1",
        theme="mintwave",
        strict="0",
        remove=False,
        dry_run=False,
        backup_suffix_fn=lambda: "TEST",
    )
    new = rc.read_text(encoding="utf-8")
    assert 'export TASKX_NEON="1"' in new
    assert 'export TASKX_THEME="mintwave"' in new
    assert 'export TASKX_STRICT="0"' in new


def test_malformed_markers_refuse(tmp_path: Path) -> None:
    rc = tmp_path / "rc"
    rc.write_text(f"{MARKER_BEGIN}\nexport TASKX_NEON=\"1\"\n", encoding="utf-8")

    with pytest.raises(ValueError):
        persist_rc_file(
            path=rc,
            neon="1",
            theme="mintwave",
            strict="0",
            remove=False,
            dry_run=True,
        )


def test_cli_rejects_invalid_theme(tmp_path: Path) -> None:
    """Test that the CLI rejects invalid themes to prevent shell injection."""
    runner = CliRunner()
    rc = tmp_path / "rc"

    # Test malicious theme with shell metacharacters
    result = runner.invoke(
        app,
        ["neon", "persist", "--theme", "malicious$(whoami)", "--path", str(rc)],
    )
    assert result.exit_code == 2
    assert "Unknown theme:" in result.output
    assert not rc.exists()  # File should not be created

    # Test malicious theme with semicolon
    result = runner.invoke(
        app,
        ["neon", "persist", "--theme", "evil; rm -rf /", "--path", str(rc)],
    )
    assert result.exit_code == 2
    assert "Unknown theme:" in result.output
    assert not rc.exists()

    # Test valid theme
    result = runner.invoke(
        app,
        ["neon", "persist", "--theme", "mintwave", "--path", str(rc)],
    )
    assert result.exit_code == 0
    assert "Unknown theme:" not in result.output

