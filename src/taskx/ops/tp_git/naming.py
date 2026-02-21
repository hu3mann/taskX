"""Deterministic naming helpers for taskx tp git workflows."""

from __future__ import annotations

import re
from pathlib import Path

from taskx.ops.tp_git.types import TpTarget

_SLUG_NON_ALLOWED = re.compile(r"[^a-z0-9-]+")
_SLUG_MULTI_DASH = re.compile(r"-{2,}")


def normalize_slug(value: str) -> str:
    """Normalize free-form slug to lowercase dash form."""
    slug = value.strip().lower().replace(" ", "-")
    slug = _SLUG_NON_ALLOWED.sub("-", slug)
    slug = _SLUG_MULTI_DASH.sub("-", slug).strip("-")
    return slug or "task"


def build_tp_branch(tp_id: str, slug: str) -> str:
    """Build deterministic TP branch name."""
    normalized = normalize_slug(slug)
    return f"tp/{tp_id}-{normalized}"


def build_worktree_path(repo_root: Path, tp_id: str) -> Path:
    """Build deterministic TP worktree path under repo root."""
    return (repo_root / ".worktrees" / tp_id).resolve()


def resolve_target(repo_root: Path, tp_id: str, slug: str) -> TpTarget:
    """Resolve deterministic branch/worktree target."""
    normalized = normalize_slug(slug)
    return TpTarget(
        repo_root=repo_root.resolve(),
        tp_id=tp_id,
        slug=normalized,
        branch=build_tp_branch(tp_id, normalized),
        worktree_path=build_worktree_path(repo_root, tp_id),
    )
