"""Command runners for TP git workflows."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExecResult:
    """Result envelope for subprocess execution."""

    argv: tuple[str, ...]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str


class ExecError(RuntimeError):
    """Raised when a command returns non-zero in check mode."""

    def __init__(self, result: ExecResult):
        rendered = " ".join(result.argv)
        detail = (result.stderr or result.stdout).strip()
        super().__init__(f"command failed ({result.returncode}): {rendered}\n{detail}")
        self.result = result


def run_command(
    argv: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> ExecResult:
    """Run command and return structured result."""
    completed = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
    result = ExecResult(
        argv=tuple(argv),
        cwd=cwd.resolve(),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and result.returncode != 0:
        raise ExecError(result)
    return result


def run_git(
    args: list[str],
    *,
    repo_root: Path,
    check: bool = True,
) -> ExecResult:
    """Run git command rooted at repo."""
    return run_command(["git", *args], cwd=repo_root, check=check)
