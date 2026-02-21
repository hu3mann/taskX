"""Types for taskx tp git workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TpTarget:
    """Deterministic target addresses for a TP branch/worktree."""

    repo_root: Path
    tp_id: str
    slug: str
    branch: str
    worktree_path: Path
