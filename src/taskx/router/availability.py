"""Load and validate router availability configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml  # type: ignore[import-untyped]

from taskx.router.types import (
    CONTEXT_WINDOWS,
    COST_TIERS,
    AvailabilityConfig,
    ModelSpec,
    RoutePolicy,
    RunnerSpec,
)

if TYPE_CHECKING:
    from pathlib import Path

# Keep this literal deterministic and sorted in write path.
AVAILABILITY_CONFIG_TEMPLATE: dict[str, Any] = {
    "models": {
        "gpt-5.1-mini": {
            "strengths": ["cheap", "docs", "routing"],
            "cost_tier": "cheap",
            "context": "medium",
        },
        "gpt-5.2": {
            "strengths": ["correctness", "gates", "finalization"],
            "cost_tier": "medium",
            "context": "medium",
        },
        "gpt-5.3-codex": {
            "strengths": ["code_edit", "wide_edit_surface", "tests"],
            "cost_tier": "high",
            "context": "large",
        },
        "haiku-4.5": {
            "strengths": ["cheap", "docs", "summaries"],
            "cost_tier": "cheap",
            "context": "small",
        },
        "sonnet-4.55": {
            "strengths": ["code_edit", "tests", "balanced"],
            "cost_tier": "medium",
            "context": "large",
        },
    },
    "runners": {
        "claude_code": {
            "available": True,
            "strengths": ["code_edit", "iterative_refactor", "tests"],
        },
        "codex_desktop": {
            "available": True,
            "strengths": ["code_edit", "planning", "tests"],
        },
        "copilot_cli": {
            "available": True,
            "strengths": ["quick_commands", "cheap_flows", "automation"],
        },
        "google_jules": {
            "available": True,
            "strengths": ["context_awareness", "file_system", "reasoning"],
        },
    },
    "policy": {
        "require_explain": True,
        "stop_on_ambiguity": True,
        "max_cost_tier": "high",
        "escalation_ladder": ["gpt-5.1-mini", "haiku-4.5", "sonnet-4.55", "gpt-5.3-codex"],
        "max_escalations": 2,
        "min_total_score": 50,
    },
}


AVAILABILITY_REASON_MISSING = "AVAILABILITY_MISSING"
AVAILABILITY_REASON_PARSE_ERROR = "AVAILABILITY_PARSE_ERROR"
AVAILABILITY_REASON_SCHEMA_INVALID = "AVAILABILITY_SCHEMA_INVALID"


class AvailabilityError(ValueError):
    """Availability configuration validation error."""

    reason_code: str

    def __init__(self, message: str, reason_code: str = AVAILABILITY_REASON_SCHEMA_INVALID) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def availability_path_for_repo(repo_root: Path) -> Path:
    """Return canonical availability file path for a repository."""
    return repo_root.resolve() / ".taskx" / "runtime" / "availability.yaml"


def ensure_default_availability(repo_root: Path, *, force: bool = False) -> Path:
    """Create default availability YAML deterministically."""
    output_path = availability_path_for_repo(repo_root)
    if output_path.exists() and not force:
        raise FileExistsError(f"Availability file already exists: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(AVAILABILITY_CONFIG_TEMPLATE, sort_keys=True)
    output_path.write_text(rendered, encoding="utf-8")
    return output_path


def load_availability(repo_root: Path) -> AvailabilityConfig:
    """Load, normalize, and validate repository availability config."""
    path = availability_path_for_repo(repo_root)
    if not path.exists():
        raise AvailabilityError(
            f"Missing availability config at {path}. Run `taskx route init --repo-root {repo_root}` first.",
            AVAILABILITY_REASON_MISSING,
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AvailabilityError(
            f"availability.yaml parse error: {exc}",
            AVAILABILITY_REASON_PARSE_ERROR,
        ) from exc
    if not isinstance(raw, dict):
        raise AvailabilityError(
            "availability.yaml parse error: expected mapping at top level",
            AVAILABILITY_REASON_PARSE_ERROR,
        )

    models_raw = raw.get("models")
    runners_raw = raw.get("runners")
    policy_raw = raw.get("policy")

    if not isinstance(models_raw, dict) or not models_raw:
        raise AvailabilityError("availability.yaml missing required non-empty `models` mapping")
    if not isinstance(runners_raw, dict) or not runners_raw:
        raise AvailabilityError("availability.yaml missing required non-empty `runners` mapping")
    if not isinstance(policy_raw, dict):
        raise AvailabilityError("availability.yaml missing required `policy` mapping")

    models: dict[str, ModelSpec] = {}
    for model_name in sorted(models_raw):
        entry = models_raw[model_name]
        if not isinstance(entry, dict):
            raise AvailabilityError(f"model `{model_name}` must be a mapping")
        strengths = _normalize_string_list(entry.get("strengths"), f"models.{model_name}.strengths")
        cost_tier = str(entry.get("cost_tier", "")).strip().lower()
        context = str(entry.get("context", "")).strip().lower()
        if cost_tier not in COST_TIERS:
            raise AvailabilityError(
                f"models.{model_name}.cost_tier must be one of {COST_TIERS}, got `{cost_tier}`"
            )
        if context not in CONTEXT_WINDOWS:
            raise AvailabilityError(
                f"models.{model_name}.context must be one of {CONTEXT_WINDOWS}, got `{context}`"
            )
        models[model_name] = ModelSpec(
            name=model_name,
            strengths=tuple(strengths),
            cost_tier=cost_tier,
            context=context,
        )

    runners: dict[str, RunnerSpec] = {}
    for runner_name in sorted(runners_raw):
        entry = runners_raw[runner_name]
        if not isinstance(entry, dict):
            raise AvailabilityError(f"runner `{runner_name}` must be a mapping")
        available = bool(entry.get("available", False))
        strengths = _normalize_string_list(entry.get("strengths"), f"runners.{runner_name}.strengths")
        runners[runner_name] = RunnerSpec(
            name=runner_name,
            available=available,
            strengths=tuple(strengths),
        )

    policy = _normalize_policy(policy_raw)
    return AvailabilityConfig(models=models, runners=runners, policy=policy, path=path)


def _normalize_policy(policy_raw: dict[str, Any]) -> RoutePolicy:
    """Normalize route policy with deterministic defaults."""
    require_explain = bool(policy_raw.get("require_explain", True))
    stop_on_ambiguity = bool(policy_raw.get("stop_on_ambiguity", True))

    max_cost_tier = str(policy_raw.get("max_cost_tier", "high")).strip().lower()
    if max_cost_tier not in COST_TIERS:
        raise AvailabilityError(f"policy.max_cost_tier must be one of {COST_TIERS}, got `{max_cost_tier}`")

    ladder = _normalize_string_list_preserve_order(
        policy_raw.get("escalation_ladder", []),
        "policy.escalation_ladder",
    )
    max_escalations = int(policy_raw.get("max_escalations", 2))
    min_total_score = int(policy_raw.get("min_total_score", 50))

    if max_escalations < 0:
        raise AvailabilityError("policy.max_escalations must be >= 0")

    return RoutePolicy(
        require_explain=require_explain,
        stop_on_ambiguity=stop_on_ambiguity,
        max_cost_tier=max_cost_tier,
        escalation_ladder=tuple(ladder),
        max_escalations=max_escalations,
        min_total_score=min_total_score,
    )


def _normalize_string_list(value: Any, field_name: str) -> list[str]:
    """Normalize a list of strings with stable ordering."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise AvailabilityError(f"{field_name} must be a list of strings")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise AvailabilityError(f"{field_name} must be a list of strings")
        normalized.append(item.strip())

    return sorted({item for item in normalized if item})


def _normalize_string_list_preserve_order(value: Any, field_name: str) -> list[str]:
    """Normalize list of strings while preserving declaration order."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise AvailabilityError(f"{field_name} must be a list of strings")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise AvailabilityError(f"{field_name} must be a list of strings")
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            normalized.append(cleaned)

    return normalized


DEFAULT_ROUTE_POLICY = _normalize_policy(AVAILABILITY_CONFIG_TEMPLATE["policy"])


def default_route_policy() -> RoutePolicy:
    """Return the deterministic default route policy."""

    return DEFAULT_ROUTE_POLICY
