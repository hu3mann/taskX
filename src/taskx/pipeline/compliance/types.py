"""Compliance gate types."""

from dataclasses import dataclass


@dataclass
class Violation:
    """Single compliance violation."""

    type: str  # allowlist_violation, missing_verification_evidence, etc.
    message: str
    files: list[str]


@dataclass
class AllowlistDiff:
    """Result of allowlist compliance check."""

    run_id: str
    task_id: str
    task_title: str
    allowlist: list[str]
    diff_mode_used: str
    allowed_files: list[str]
    disallowed_files: list[str]
    violations: list[Violation]
    diff_hash: str
