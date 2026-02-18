from __future__ import annotations

import difflib
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import TypeVar

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

_T = TypeVar("_T")

console = Console()

NEON_LINES: list[str] = [
    "████████╗ █████╗ ███████╗██╗  ██╗██╗  ██╗",
    "╚══██╔══╝██╔══██╗██╔════╝╚██╗██╔╝╚██╗██╔╝",
    "   ██║   ███████║███████╗ ╚███╔╝  ╚███╔╝ ",
    "   ██║   ██╔══██║╚════██║ ██╔██╗  ██╔██╗ ",
    "   ██║   ██║  ██║███████║██╔╝ ██╗██╔╝ ██╗",
    "   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝",
]

THEMES: dict[str, list[str]] = {
    "mintwave": [
        "bright_cyan",
        "cyan",
        "bright_blue",
        "blue",
        "bright_green",
        "green",
    ],
    "cyberpunk": [
        "bright_magenta",
        "magenta",
        "bright_cyan",
        "cyan",
        "bright_yellow",
        "yellow",
    ],
    "ultraviolet": [
        "magenta",
        "bright_magenta",
        "blue",
        "bright_blue",
        "cyan",
        "bright_cyan",
    ],
    "magma": [
        "bright_red",
        "red",
        "bright_yellow",
        "yellow",
        "bright_magenta",
        "magenta",
    ],
    "toxic_lime": [
        "bright_green",
        "green",
        "bright_yellow",
        "yellow",
        "bright_cyan",
        "cyan",
    ],
}

NEON_RC_MARKER_BEGIN = "# >>> TASKX NEON BEGIN >>>"
NEON_RC_MARKER_END = "# <<< TASKX NEON END <<<"


def neon_enabled() -> bool:
    return os.getenv("TASKX_NEON", "1") == "1"


def strict_enabled() -> bool:
    return os.getenv("TASKX_STRICT", "0") == "1"


def get_theme_name() -> str:
    return os.getenv("TASKX_THEME", "mintwave")


def get_theme_palette(theme: str | None = None) -> list[str]:
    name = theme or get_theme_name()
    return THEMES.get(name, THEMES["mintwave"])


def should_show_banner(argv: Sequence[str]) -> bool:
    if not neon_enabled():
        return False
    if len(argv) <= 1:
        return True
    if any(a in ("--help", "-h", "--version") for a in argv[1:]):
        return True
    if len(argv) >= 2 and argv[1] in ("version",):
        return True
    return False


def render_banner(theme: str | None = None) -> None:
    if not neon_enabled():
        return

    palette = get_theme_palette(theme)
    colors = cycle(palette)
    for line in NEON_LINES:
        t = Text()
        for ch in line:
            t.append(ch, style=f"bold {next(colors)}")
        console.print(t)

    console.print()
    console.print(Text("DETERMINISTIC TASK EXECUTION KERNEL", style="bold bright_white on magenta"))
    console.print(Text("NO FALLBACKS. NO RETRIES. NO GHOST BEHAVIOR.", style="bold bright_yellow on red"))
    console.print(Text("ONE INVOCATION. ONE PATH. ONE OUTCOME.", style="bold bright_cyan on blue"))
    console.print(Text(f"Theme: {theme or get_theme_name()}  Toggle: TASKX_NEON=0", style="dim"))
    console.print()


@dataclass(frozen=True)
class NeonSpinner:
    message: str

    def run(self, fn: Callable[[], _T]) -> _T:
        if not neon_enabled():
            return fn()

        with Progress(
            SpinnerColumn(style="bright_magenta"),
            TextColumn("[bold bright_cyan]{task.description}[/bold bright_cyan]"),
            transient=True,
            console=console,
        ) as prog:
            task_id = prog.add_task(self.message, total=None)
            try:
                return fn()
            finally:
                prog.update(task_id, completed=1)


def strict_violation(msg: str) -> None:
    if not strict_enabled():
        return
    console.print(Text("STRICT MODE VIOLATION", style="bold bright_white on red"))
    console.print(Text(msg, style="bold bright_red"))


def worship() -> None:
    lines = [
        "KERNEL WORSHIP ACCEPTED",
        "Show me the packet.",
        "Leave artifacts. No excuses.",
        "One path. Stay honest.",
        "Refusal is integrity.",
    ]
    if neon_enabled():
        console.print(Text(lines[0], style="bold bright_white on magenta"))
        for s in lines[1:]:
            console.print(Text(s, style="bold bright_cyan"))
        console.print()
    else:
        for s in lines:
            print(s)


def sleep_ms(delay_ms: int) -> None:
    time.sleep(max(0, delay_ms) / 1000.0)


def render_neon_rc_block(*, theme: str) -> str:
    if theme not in THEMES:
        raise ValueError(f"Unknown theme: {theme!r}. Valid themes: {', '.join(sorted(THEMES))}")
    lines = [
        NEON_RC_MARKER_BEGIN,
        "export TASKX_NEON=1",
        f'export TASKX_THEME="{theme}"',
        NEON_RC_MARKER_END,
        "",
    ]
    return "\n".join(lines)


def _locate_single_neon_block(contents: str) -> tuple[int, int] | None:
    begin_idx = contents.find(NEON_RC_MARKER_BEGIN)
    end_idx = contents.find(NEON_RC_MARKER_END)

    if begin_idx != -1 and contents.find(NEON_RC_MARKER_BEGIN, begin_idx + 1) != -1:
        raise ValueError("Multiple TASKX NEON begin markers found.")
    if end_idx != -1 and contents.find(NEON_RC_MARKER_END, end_idx + 1) != -1:
        raise ValueError("Multiple TASKX NEON end markers found.")

    if begin_idx == -1 and end_idx == -1:
        return None
    if begin_idx == -1:
        raise ValueError("Malformed TASKX NEON markers: begin marker missing.")
    if end_idx == -1:
        raise ValueError("Malformed TASKX NEON markers: end marker missing.")
    if end_idx < begin_idx:
        raise ValueError("Malformed TASKX NEON markers: end marker appears before begin marker.")

    start = contents.rfind("\n", 0, begin_idx)
    start = 0 if start == -1 else start + 1
    end_line = contents.find("\n", end_idx)
    end = len(contents) if end_line == -1 else end_line + 1
    return (start, end)


def apply_neon_rc_block(contents: str, *, block: str, remove: bool) -> tuple[str, bool]:
    span = _locate_single_neon_block(contents)

    if span is None:
        if remove:
            return contents, False
        if contents == "":
            return block, True
        prefix = contents
        if not prefix.endswith("\n"):
            prefix = f"{prefix}\n"
        if not prefix.endswith("\n\n"):
            prefix = f"{prefix}\n"
        new_contents = f"{prefix}{block}"
        return new_contents, new_contents != contents

    start, end = span
    if remove:
        new_contents = f"{contents[:start]}{contents[end:]}"
    else:
        new_contents = f"{contents[:start]}{block}{contents[end:]}"
    return new_contents, new_contents != contents


def neon_rc_unified_diff(old: str, new: str, *, path: Path) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )


def _atomic_write(path: Path, content: str) -> None:
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            prefix=f".{path.name}.",
            suffix=".taskx.tmp",
        ) as tmp_file:
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file if it exists
        if "tmp_path" in locals() and tmp_path.exists():
            tmp_path.unlink()
        raise


@dataclass(frozen=True)
class NeonRcPersistResult:
    path: Path
    changed: bool
    diff: str
    backup_path: Path | None


def persist_neon_rc_file(
    *,
    path: Path,
    theme: str,
    remove: bool,
    dry_run: bool,
) -> NeonRcPersistResult:
    if theme not in THEMES:
        raise ValueError(f"Unknown theme: {theme!r}. Valid themes: {', '.join(sorted(THEMES))}")
    try:
        old = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        raise OSError(f"Failed to read rc file {path}: {exc}") from exc

    block = render_neon_rc_block(theme=theme)
    new, changed = apply_neon_rc_block(old, block=block, remove=remove)
    diff = neon_rc_unified_diff(old, new, path=path)

    if dry_run or not changed:
        return NeonRcPersistResult(path=path, changed=changed, diff=diff, backup_path=None)

    backup_path = path.with_name(f"{path.name}.taskx.bak")
    try:
        _atomic_write(backup_path, old)
    except OSError as exc:
        raise OSError(f"Failed to write backup rc file {backup_path}: {exc}") from exc

    try:
        _atomic_write(path, new)
    except OSError as exc:
        raise OSError(f"Failed to write rc file {path}: {exc}") from exc

    return NeonRcPersistResult(path=path, changed=changed, diff=diff, backup_path=backup_path)
