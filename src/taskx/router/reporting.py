"""Deterministic route report writers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from taskx.router.handoff import render_handoff_markdown
from taskx.router.types import PlannedStep, RoutePlan, RoutePolicy, TopCandidate


def route_plan_to_dict(plan: RoutePlan) -> dict[str, Any]:
    """Convert route plan dataclass to deterministic JSON payload."""
    return {
        "status": plan.status,
        "repo_root": str(plan.repo_root),
        "packet_path": str(plan.packet_path),
        "availability_path": str(plan.availability_path),
        "policy": {
            "require_explain": plan.policy.require_explain,
            "stop_on_ambiguity": plan.policy.stop_on_ambiguity,
            "max_cost_tier": plan.policy.max_cost_tier,
            "escalation_ladder": list(plan.policy.escalation_ladder),
            "max_escalations": plan.policy.max_escalations,
            "min_total_score": plan.policy.min_total_score,
        },
        "refusal_reasons": list(plan.refusal_reasons),
        "steps": [
            {
                "step": step.step,
                "runner": step.runner,
                "model": step.model,
                "confidence": float(f"{step.confidence:.2f}"),
                "scores": {
                    "runner_fit": step.scores["runner_fit"],
                    "model_fit": step.scores["model_fit"],
                    "cost_penalty": step.scores["cost_penalty"],
                    "confidence_penalty": step.scores["confidence_penalty"],
                    "total": step.scores["total"],
                },
                "reasons": list(step.reasons),
                "candidates_top3": [
                    {
                        "runner": item.runner,
                        "model": item.model,
                        "total": item.total,
                    }
                    for item in step.candidates_top3
                ],
            }
            for step in plan.steps
        ],
    }


def route_plan_from_dict(payload: dict[str, Any]) -> RoutePlan:
    """Load route plan dataclass from deterministic JSON payload."""
    policy_raw = payload["policy"]
    policy = RoutePolicy(
        require_explain=bool(policy_raw["require_explain"]),
        stop_on_ambiguity=bool(policy_raw["stop_on_ambiguity"]),
        max_cost_tier=str(policy_raw["max_cost_tier"]),
        escalation_ladder=tuple(policy_raw["escalation_ladder"]),
        max_escalations=int(policy_raw["max_escalations"]),
        min_total_score=int(policy_raw["min_total_score"]),
    )

    steps: list[PlannedStep] = []
    for step_raw in payload["steps"]:
        top3 = tuple(
            TopCandidate(
                runner=str(candidate["runner"]),
                model=str(candidate["model"]),
                total=int(candidate["total"]),
            )
            for candidate in step_raw.get("candidates_top3", [])
        )
        steps.append(
            PlannedStep(
                step=str(step_raw["step"]),
                runner=step_raw.get("runner"),
                model=step_raw.get("model"),
                confidence=float(step_raw.get("confidence", 0.0)),
                scores={
                    "runner_fit": int(step_raw["scores"]["runner_fit"]),
                    "model_fit": int(step_raw["scores"]["model_fit"]),
                    "cost_penalty": int(step_raw["scores"]["cost_penalty"]),
                    "confidence_penalty": int(step_raw["scores"]["confidence_penalty"]),
                    "total": int(step_raw["scores"]["total"]),
                },
                reasons=tuple(step_raw.get("reasons", [])),
                candidates_top3=top3,
            )
        )

    return RoutePlan(
        status=str(payload["status"]),
        repo_root=Path(payload["repo_root"]),
        packet_path=Path(payload["packet_path"]),
        availability_path=Path(payload["availability_path"]),
        policy=policy,
        steps=tuple(steps),
        refusal_reasons=tuple(payload.get("refusal_reasons", [])),
    )


def render_route_plan_markdown(plan: RoutePlan) -> str:
    """Render deterministic human-readable route plan summary."""
    lines = [
        "# ROUTE_PLAN",
        "",
        f"- status: {plan.status}",
        f"- repo_root: {plan.repo_root}",
        f"- packet_path: {plan.packet_path}",
        f"- availability_path: {plan.availability_path}",
        "",
        "## Policy",
        "",
        f"- require_explain: {plan.policy.require_explain}",
        f"- stop_on_ambiguity: {plan.policy.stop_on_ambiguity}",
        f"- max_cost_tier: {plan.policy.max_cost_tier}",
        f"- escalation_ladder: {', '.join(plan.policy.escalation_ladder)}",
        f"- max_escalations: {plan.policy.max_escalations}",
        f"- min_total_score: {plan.policy.min_total_score}",
        "",
        "## Decisions",
        "",
        "| step | runner | model | confidence | total |",
        "| --- | --- | --- | --- | --- |",
    ]

    for step in plan.steps:
        lines.append(
            f"| {step.step} | {step.runner or 'none'} | {step.model or 'none'} | {step.confidence:.2f} | {step.scores['total']} |"
        )

    lines.append("")
    if plan.refusal_reasons:
        lines.extend(["## Refusals", ""])
        for reason in plan.refusal_reasons:
            lines.append(f"- {reason}")
        lines.append("")

    return "\n".join(lines)


def write_route_artifacts(
    *,
    plan: RoutePlan,
    plan_json_path: Path,
    plan_md_path: Path,
    handoff_md_path: Path,
) -> None:
    """Write all deterministic router artifacts."""
    plan_json_path.parent.mkdir(parents=True, exist_ok=True)
    plan_md_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_md_path.parent.mkdir(parents=True, exist_ok=True)

    plan_json_path.write_text(
        json.dumps(route_plan_to_dict(plan), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    plan_md_path.write_text(render_route_plan_markdown(plan), encoding="utf-8")
    handoff_md_path.write_text(render_handoff_markdown(plan), encoding="utf-8")
