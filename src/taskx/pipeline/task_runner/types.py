"""Task runner types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskPacketInfo:
    """Parsed task packet information."""

    id: str
    title: str
    path: str
    sha256: str
    allowlist: list[str]
    sources: list[str]
    verification_commands: list[str]
    sections: dict[str, str]


@dataclass
class RunWorkspace:
    """Run workspace information."""

    root: str
    files: list[dict[str, str]]
