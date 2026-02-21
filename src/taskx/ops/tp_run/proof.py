"""Proof pack writer primitives for taskx tp run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProofSkeleton:
    """Minimal shape for proof-pack path scaffolding."""

    repo_root: Path
    tp_id: str
    run_id: str
