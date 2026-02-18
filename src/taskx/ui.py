from __future__ import annotations

import os
import time
from dataclasses import dataclass
from itertools import cycle
from typing import Callable, Sequence, TypeVar

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

