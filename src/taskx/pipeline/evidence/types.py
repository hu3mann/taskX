"""Evidence collector types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Claim:
    """Extracted claim from run evidence."""

    claim_id: str
    claim_type: str
    text: str
    evidence_source: str
    confidence: float


@dataclass
class RunStatus:
    """Status of run execution."""

    checklist_completed: bool
    verification_commands_listed: bool
    verification_outputs_present: bool
    anomalies: list[str]
