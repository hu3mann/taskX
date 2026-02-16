"""Router domain types for assisted routing v1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_STEPS: tuple[str, ...] = (
    "compile-tasks",
    "run-task",
    "collect-evidence",
    "gate-allowlist",
    "commit-run",
    "finish",
)

DEFAULT_AVAILABILITY_RELATIVE_PATH = Path(".taskx/runtime/availability.yaml")
DEFAULT_PLAN_RELATIVE_PATH = Path("out/taskx_route/ROUTE_PLAN.json")
DEFAULT_PLAN_MARKDOWN_RELATIVE_PATH = Path("out/taskx_route/ROUTE_PLAN.md")
DEFAULT_HANDOFF_RELATIVE_PATH = Path("out/taskx_route/HANDOFF.md")

COST_TIERS: tuple[str, ...] = ("cheap", "medium", "high")
CONTEXT_WINDOWS: tuple[str, ...] = ("small", "medium", "large")
RUNNER_NAMES: tuple[str, ...] = ("claude_code", "codex_desktop", "copilot_cli")


@dataclass(frozen=True)
class ModelSpec:
    """Configured model capability and cost profile."""

    name: str
    strengths: tuple[str, ...]
    cost_tier: str
    context: str


@dataclass(frozen=True)
class RunnerSpec:
    """Configured runner capability availability."""

    name: str
    available: bool
    strengths: tuple[str, ...]


@dataclass(frozen=True)
class RoutePolicy:
    """Deterministic route policy knobs."""

    require_explain: bool
    stop_on_ambiguity: bool
    max_cost_tier: str
    escalation_ladder: tuple[str, ...]
    max_escalations: int
    min_total_score: int


@dataclass(frozen=True)
class AvailabilityConfig:
    """Normalized router availability configuration."""

    models: dict[str, ModelSpec]
    runners: dict[str, RunnerSpec]
    policy: RoutePolicy
    path: Path


@dataclass(frozen=True)
class CandidateScore:
    """Deterministic score details for a single runner/model candidate."""

    runner: str
    model: str
    runner_fit: int
    model_fit: int
    cost_penalty: int
    confidence_penalty: int
    total: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TopCandidate:
    """Compact top candidate projection."""

    runner: str
    model: str
    total: int


@dataclass(frozen=True)
class PlannedStep:
    """Selected route decision for one lifecycle step."""

    step: str
    runner: str | None
    model: str | None
    confidence: float
    scores: dict[str, int]
    reasons: tuple[str, ...]
    candidates_top3: tuple[TopCandidate, ...]


@dataclass(frozen=True, slots=True)
class RefusalReason:
    reason_code: str | None
    message: str
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.reason_code is not None and not self.reason_code:
            raise ValueError("reason_code must be provided when not None")
        if not self.message:
            raise ValueError("message must be provided")

    def to_dict(self) -> dict[str, str | None]:
        data: dict[str, str | None] = {
            "reason_code": self.reason_code,
            "message": self.message,
        }
        if self.detail is not None:
            data["detail"] = self.detail
        return data

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class RoutePlan:
    """Full deterministic route plan."""

    status: str
    repo_root: Path
    packet_path: Path
    availability_path: Path
    policy: RoutePolicy
    steps: tuple[PlannedStep, ...]
    refusal_reasons: tuple[RefusalReason, ...]
