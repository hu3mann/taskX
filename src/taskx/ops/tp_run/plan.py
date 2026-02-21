"""Execution plan primitives for taskx tp run."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunSkeleton:
    """Minimal shape for tp run planning during scaffold stage."""

    tp_id: str
    slug: str
