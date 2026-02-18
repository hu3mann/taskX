from __future__ import annotations

from pathlib import Path

from taskx.ui import (
    NEON_RC_MARKER_BEGIN,
    NEON_RC_MARKER_END,
    persist_neon_rc_file,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_first_insert_block_appears_once(tmp_path: Path) -> None:
    rc = tmp_path / "shellrc"
    rc.write_text("export KEEP=1\n", encoding="utf-8")

    result = persist_neon_rc_file(path=rc, theme="mintwave", remove=False, dry_run=False)

    content = _read(rc)
    assert result.changed is True
    assert content.count(NEON_RC_MARKER_BEGIN) == 1
    assert content.count(NEON_RC_MARKER_END) == 1
    assert "export KEEP=1" in content
    assert "export TASKX_NEON=1" in content
    assert 'export TASKX_THEME="mintwave"' in content


def test_second_insert_does_not_duplicate_block(tmp_path: Path) -> None:
    rc = tmp_path / "shellrc"
    persist_neon_rc_file(path=rc, theme="mintwave", remove=False, dry_run=False)
    first = _read(rc)

    result = persist_neon_rc_file(path=rc, theme="mintwave", remove=False, dry_run=False)

    assert result.changed is False
    assert result.backup_path is None
    assert _read(rc) == first
    assert _read(rc).count(NEON_RC_MARKER_BEGIN) == 1


def test_update_theme_replaces_existing_block(tmp_path: Path) -> None:
    rc = tmp_path / "shellrc"
    persist_neon_rc_file(path=rc, theme="mintwave", remove=False, dry_run=False)

    persist_neon_rc_file(path=rc, theme="magma", remove=False, dry_run=False)

    content = _read(rc)
    assert content.count(NEON_RC_MARKER_BEGIN) == 1
    assert 'export TASKX_THEME="magma"' in content
    assert 'export TASKX_THEME="mintwave"' not in content


def test_dry_run_does_not_mutate_file(tmp_path: Path) -> None:
    rc = tmp_path / "shellrc"
    rc.write_text("export KEEP=1\n", encoding="utf-8")
    original = _read(rc)

    result = persist_neon_rc_file(path=rc, theme="mintwave", remove=False, dry_run=True)

    assert result.changed is True
    assert _read(rc) == original
    assert result.backup_path is None
    assert rc.with_name(f"{rc.name}.taskx.bak").exists() is False


def test_remove_removes_only_marker_block(tmp_path: Path) -> None:
    rc = tmp_path / "shellrc"
    rc.write_text("export KEEP_BEFORE=1\n", encoding="utf-8")
    persist_neon_rc_file(path=rc, theme="mintwave", remove=False, dry_run=False)
    with rc.open("a", encoding="utf-8") as handle:
        handle.write("export KEEP_AFTER=1\n")

    persist_neon_rc_file(path=rc, theme="mintwave", remove=True, dry_run=False)

    content = _read(rc)
    assert NEON_RC_MARKER_BEGIN not in content
    assert NEON_RC_MARKER_END not in content
    assert "export KEEP_BEFORE=1" in content
    assert "export KEEP_AFTER=1" in content


def test_backup_created_only_on_mutation(tmp_path: Path) -> None:
    rc = tmp_path / "shellrc"
    backup = rc.with_name(f"{rc.name}.taskx.bak")

    first = persist_neon_rc_file(path=rc, theme="mintwave", remove=False, dry_run=False)
    assert first.backup_path == backup
    assert backup.exists()

    second = persist_neon_rc_file(path=rc, theme="mintwave", remove=False, dry_run=False)
    assert second.backup_path is None
