from __future__ import annotations

import difflib
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

MARKER_BEGIN = "# >>> TASKX NEON BEGIN >>>"
MARKER_END = "# <<< TASKX NEON END <<<"


def render_block(*, neon: str, theme: str, strict: str) -> str:
    lines = [
        MARKER_BEGIN,
        f'export TASKX_NEON="{neon}"',
        f'export TASKX_THEME="{theme}"',
        f'export TASKX_STRICT="{strict}"',
        MARKER_END,
        "",
    ]
    return "\n".join(lines)


def apply_managed_block(contents: str, *, block: str, remove: bool) -> tuple[str, bool]:
    begin_idx = contents.find(MARKER_BEGIN)
    end_idx = contents.find(MARKER_END)

    # Reject files that contain multiple managed blocks, as behavior would be ambiguous.
    if begin_idx != -1:
        next_begin_idx = contents.find(MARKER_BEGIN, begin_idx + len(MARKER_BEGIN))
        if next_begin_idx != -1:
            raise ValueError("Multiple TASKX NEON begin markers found.")
    if end_idx != -1:
        next_end_idx = contents.find(MARKER_END, end_idx + len(MARKER_END))
        if next_end_idx != -1:
            raise ValueError("Multiple TASKX NEON end markers found.")
    if begin_idx == -1 and end_idx == -1:
        if remove:
            return contents, False
        prefix = "" if contents.endswith("\n") or contents == "" else "\n"
        return contents + prefix + block, True

    if begin_idx == -1 or end_idx == -1 or end_idx < begin_idx:
        if begin_idx == -1 and end_idx != -1:
            raise ValueError("Malformed TASKX NEON markers: begin marker missing.")
        if end_idx == -1 and begin_idx != -1:
            raise ValueError("Malformed TASKX NEON markers: end marker missing.")
        if end_idx < begin_idx:
            raise ValueError(
                "Malformed TASKX NEON markers: markers found in wrong order (end before begin)."
            )
        # Fallback for any unexpected mismatch.
        raise ValueError("Malformed TASKX NEON markers (begin/end mismatch).")

    end_idx = end_idx + len(MARKER_END)

    before = contents[:begin_idx]
    after = contents[end_idx:]
    if remove:
        # Remove the block and any immediate trailing newline(s) to avoid leaving gaps.
        new_contents = (before.rstrip("\n") + "\n" + after.lstrip("\n")).rstrip("\n") + "\n"
        return new_contents if new_contents != "\n" else "", True

    new_contents = before + block + after.lstrip("\n")
    return new_contents, new_contents != contents


def unified_diff(old: str, new: str, *, path: Path) -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=str(path),
        tofile=str(path),
    )
    return "".join(diff)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.taskx.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _default_backup_suffix() -> str:
    """Generate a timestamp-based backup suffix with microsecond precision.

    Uses format: YYYYMMDDHHMMSS_MMMMMM (e.g., 20260218074700_123456)
    This prevents backup file collisions when persist_rc_file is called
    multiple times within the same second.
    """
    import datetime
    now = datetime.datetime.now()
    return now.strftime("%Y%m%d%H%M%S") + f"_{now.microsecond:06d}"


@dataclass(frozen=True)
class PersistResult:
    path: Path
    changed: bool
    diff: str
    backup_path: Path | None


def persist_rc_file(
    *,
    path: Path,
    neon: str,
    theme: str,
    strict: str,
    remove: bool,
    dry_run: bool,
    backup_suffix_fn: Callable[[], str] = _default_backup_suffix,
) -> PersistResult:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    block = render_block(neon=neon, theme=theme, strict=strict)
    new, changed = apply_managed_block(old, block=block, remove=remove)
    diff = unified_diff(old, new, path=path)

    if dry_run:
        return PersistResult(path=path, changed=changed, diff=diff, backup_path=None)

    backup_path: Path | None = None
    if changed:
        # Create a backup of the previous contents before modifying the file.
        backup_path = path.with_name(f"{path.name}.taskx.bak.{backup_suffix_fn()}")
        _atomic_write(backup_path, old)
    _atomic_write(path, new)
    return PersistResult(path=path, changed=changed, diff=diff, backup_path=backup_path)

