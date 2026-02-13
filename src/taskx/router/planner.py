"""Deterministic router planner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from taskx.router.availability import load_availability
from taskx.router.scoring import score_step_candidates, score_to_confidence
from taskx.router.types import DEFAULT_STEPS, PlannedStep, RoutePlan, TopCandidate

if TYPE_CHECKING:
    from pathlib import Path


def parse_steps(steps: list[str] | None) -> tuple[str, ...]:
    """Parse CLI step flags (repeatable and comma-separated)."""
    if not steps:
        return DEFAULT_STEPS

    parsed: list[str] = []
    for raw in steps:
        for item in raw.split(","):
            value = item.strip()
            if value:
                parsed.append(value)

    if not parsed:
        return DEFAULT_STEPS
    return tuple(parsed)


def extract_router_hints(packet_path: Path) -> dict[str, str]:
    """Safely parse shallow ROUTER_HINTS block from packet markdown."""
    text = packet_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_hints = False
    hints: dict[str, str] = {}

    for line in lines:
        if not in_hints:
            if line.strip().startswith("ROUTER_HINTS:"):
                in_hints = True
            continue

        if not line.strip():
            break
        if line.lstrip().startswith("#"):
            break
        if not line.startswith(" ") and not line.startswith("\t"):
            break
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        normalized_key = key.strip().lower()
        normalized_value = value.strip().strip("\"'")
        if normalized_key:
            hints[normalized_key] = normalized_value

    return dict(sorted(hints.items()))


def build_route_plan(
    *,
    repo_root: Path,
    packet_path: Path,
    steps: tuple[str, ...] | None = None,
) -> RoutePlan:
    """Build deterministic plan for packet + steps."""
    resolved_repo_root = repo_root.resolve()
    resolved_packet = packet_path.resolve()
    availability = load_availability(resolved_repo_root)

    planned_steps = steps or DEFAULT_STEPS
    hints = extract_router_hints(resolved_packet)

    decisions: list[PlannedStep] = []
    refusal_reasons: list[str] = []

    for step in planned_steps:
        candidates = score_step_candidates(step=step, availability=availability, hints=hints)

        if not candidates:
            decisions.append(
                PlannedStep(
                    step=step,
                    runner=None,
                    model=None,
                    confidence=0.0,
                    scores={
                        "runner_fit": 0,
                        "model_fit": 0,
                        "cost_penalty": 0,
                        "confidence_penalty": 0,
                        "total": 0,
                    },
                    reasons=("no_available_runner_model_pairs",),
                    candidates_top3=(),
                )
            )
            refusal_reasons.append(f"No available runner/model candidates for step `{step}`")
            continue

        top = candidates[0]
        confidence = score_to_confidence(top.total)
        top3 = tuple(
            TopCandidate(runner=item.runner, model=item.model, total=item.total)
            for item in candidates[:3]
        )

        if top.total < availability.policy.min_total_score:
            refusal_reasons.append(
                f"Step `{step}` below score threshold: {top.total} < {availability.policy.min_total_score}"
            )

        decisions.append(
            PlannedStep(
                step=step,
                runner=top.runner,
                model=top.model,
                confidence=confidence,
                scores={
                    "runner_fit": top.runner_fit,
                    "model_fit": top.model_fit,
                    "cost_penalty": top.cost_penalty,
                    "confidence_penalty": top.confidence_penalty,
                    "total": top.total,
                },
                reasons=top.reasons,
                candidates_top3=top3,
            )
        )

    status = "refused" if refusal_reasons else "ok"
    return RoutePlan(
        status=status,
        repo_root=resolved_repo_root,
        packet_path=resolved_packet,
        availability_path=availability.path,
        policy=availability.policy,
        steps=tuple(decisions),
        refusal_reasons=tuple(sorted(set(refusal_reasons))),
    )


def explain_step(plan: RoutePlan, step: str) -> str:
    """Render deterministic explanation for one planned step."""
    for item in plan.steps:
        if item.step != step:
            continue
        lines = [
            f"step: {item.step}",
            f"status: {plan.status}",
            f"runner: {item.runner or 'none'}",
            f"model: {item.model or 'none'}",
            f"confidence: {item.confidence:.2f}",
            f"score_total: {item.scores['total']}",
            "reasons:",
        ]
        if item.reasons:
            lines.extend(f"- {reason}" for reason in item.reasons)
        else:
            lines.append("- none")
        return "\n".join(lines)

    raise KeyError(f"Step `{step}` was not planned")
