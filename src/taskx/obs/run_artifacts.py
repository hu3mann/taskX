"""Canonical run artifact helpers for stateful TaskX commands."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from taskx.utils.repo import find_taskx_repo_root

CanonicalTimestampMode = Literal["deterministic", "now"]

TASKX_RUN_ROOT_ENV = "TASKX_RUN_ROOT"
PROJECT_IDENTITY_PATH = ".taskx/project.json"

RUN_ENVELOPE_FILENAME = "RUN_ENVELOPE.json"
RUN_IDENTITY_FILENAME = "RUN_IDENTITY.json"
EVIDENCE_FILENAME = "EVIDENCE.md"
ALLOWLIST_DIFF_FILENAME = "ALLOWLIST_DIFF.json"
VIOLATIONS_FILENAME = "VIOLATIONS.md"
PROMOTION_TOKEN_FILENAME = "PROMOTION_TOKEN.json"
PROMOTION_LEGACY_FILENAME = "PROMOTION.json"
COMMIT_RUN_FILENAME = "COMMIT_RUN.json"
WORKTREE_FILENAME = "WORKTREE.json"
COMMIT_SEQUENCE_RUN_FILENAME = "COMMIT_SEQUENCE_RUN.json"
FINISH_FILENAME = "FINISH.json"
DIRTY_STATE_FILENAME = "DIRTY_STATE.json"
DOCTOR_REPORT_FILENAME = "DOCTOR_REPORT.json"


def normalize_timestamp_mode(timestamp_mode: str) -> CanonicalTimestampMode:
    """Normalize CLI timestamp modes to canonical run-id modes."""
    normalized = timestamp_mode.strip().lower()
    if normalized in {"deterministic", "now"}:
        return normalized  # type: ignore[return-value]
    if normalized == "wallclock":
        return "now"
    raise ValueError(
        f"Unsupported timestamp mode: {timestamp_mode}. "
        "Expected one of: deterministic, now, wallclock."
    )


def to_pipeline_timestamp_mode(timestamp_mode: str) -> str:
    """Convert canonical run-id mode to existing pipeline timestamp mode values."""
    canonical_mode = normalize_timestamp_mode(timestamp_mode)
    return "deterministic" if canonical_mode == "deterministic" else "wallclock"


def get_default_run_root(
    cli_run_root: Path | None = None,
    *,
    cwd: Path | None = None,
) -> Path:
    """Resolve run-root path using canonical precedence."""
    if cli_run_root is not None:
        return cli_run_root.expanduser().resolve()

    env_root = os.getenv(TASKX_RUN_ROOT_ENV, "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()

    effective_cwd = (cwd or Path.cwd()).resolve()
    repo_root = find_taskx_repo_root(effective_cwd)
    if repo_root is not None:
        return (repo_root / "out" / "runs").resolve()

    return (effective_cwd / "out" / "runs").resolve()


def make_run_id(prefix: str, timestamp_mode: CanonicalTimestampMode) -> str:
    """Create canonical run IDs."""
    prefix_clean = prefix.strip() or "RUN"

    if timestamp_mode == "deterministic":
        return f"{prefix_clean}_DETERMINISTIC"
    if timestamp_mode == "now":
        return f"{prefix_clean}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    raise ValueError(f"Unsupported canonical timestamp mode: {timestamp_mode}")


def resolve_run_dir(
    *,
    run: Path | None,
    run_root: Path | None,
    timestamp_mode: str,
    prefix: str = "RUN",
) -> Path:
    """Resolve concrete run directory from explicit --run or canonical defaults."""
    if run is not None:
        return run.expanduser().resolve()

    root = get_default_run_root(cli_run_root=run_root)
    canonical_mode = normalize_timestamp_mode(timestamp_mode)
    return (root / make_run_id(prefix=prefix, timestamp_mode=canonical_mode)).resolve()
