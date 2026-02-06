"""Type definitions for task compilation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PacketSource:
    """Source file citation."""

    path: str  # Repo-relative
    heading_text: str | None = None


@dataclass
class TaskPacket:
    """A law-grade task packet."""

    id: str  # e.g., TP_0001
    slug: str  # kebab-case
    title: str
    priority: int  # 1-5, 1 highest
    effort: str  # S|M|L
    risk: str  # low|med|high
    depends_on: list[str] = field(default_factory=list)  # TP IDs
    allowlist: list[str] = field(default_factory=list)  # File paths/globs
    sources: list[PacketSource] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)  # Commands
    outputs: list[str] = field(default_factory=list)  # Expected artifacts
    notes: str = ""


@dataclass
class TaskQueue:
    """Complete task queue output."""

    schema_version: str
    pipeline_version: str
    generated_at: str
    inputs: dict
    packets: list[TaskPacket]
