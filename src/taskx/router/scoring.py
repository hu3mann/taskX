"""Deterministic candidate scoring for routing decisions."""

from taskx.router.types import COST_TIERS, AvailabilityConfig, CandidateScore

COST_ORDER = {name: idx for idx, name in enumerate(COST_TIERS)}


def score_step_candidates(
    *,
    step: str,
    availability: AvailabilityConfig,
    hints: dict[str, str],
) -> list[CandidateScore]:
    """Score all available runner/model pairs deterministically for one step."""
    candidates: list[CandidateScore] = []

    model_names = sorted(availability.models)
    runner_names = sorted(availability.runners)

    for runner_name in runner_names:
        runner = availability.runners[runner_name]
        if not runner.available:
            continue

        for model_name in model_names:
            model = availability.models[model_name]
            if COST_ORDER[model.cost_tier] > COST_ORDER[availability.policy.max_cost_tier]:
                continue

            runner_fit, runner_reasons = _score_runner_fit(step=step, runner_strengths=runner.strengths)
            model_fit, model_reasons = _score_model_fit(
                step=step,
                model_name=model_name,
                model_strengths=model.strengths,
                hints=hints,
            )
            cost_penalty = _cost_penalty(step=step, cost_tier=model.cost_tier)
            confidence_penalty = _confidence_penalty(step=step, model_name=model_name)
            total = runner_fit + model_fit + cost_penalty + confidence_penalty

            reasons = sorted({*runner_reasons, *model_reasons, f"cost:{model.cost_tier}"})
            candidates.append(
                CandidateScore(
                    runner=runner_name,
                    model=model_name,
                    runner_fit=runner_fit,
                    model_fit=model_fit,
                    cost_penalty=cost_penalty,
                    confidence_penalty=confidence_penalty,
                    total=total,
                    reasons=tuple(reasons),
                )
            )

    candidates.sort(key=lambda item: (-item.total, item.runner, item.model))
    return candidates


def score_to_confidence(total: int) -> float:
    """Deterministically map integer score to fixed-precision confidence."""
    raw = max(0.0, min(1.0, total / 75.0))
    return round(raw, 2)


def _score_runner_fit(*, step: str, runner_strengths: tuple[str, ...]) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 20

    strengths = set(runner_strengths)
    if step == "run-task":
        if "code_edit" in strengths:
            score += 12
            reasons.append("runner_code_edit")
        if "tests" in strengths:
            score += 8
            reasons.append("runner_tests")
    elif step == "collect-evidence":
        if "automation" in strengths:
            score += 8
            reasons.append("runner_automation")
        if "planning" in strengths:
            score += 5
            reasons.append("runner_planning")
    elif step in {"gate-allowlist", "commit-run", "finish"}:
        if "tests" in strengths:
            score += 10
            reasons.append("runner_verification")
    elif step == "compile-tasks" or step.startswith("docs/") or step == "route explain":
        if "cheap_flows" in strengths:
            score += 8
            reasons.append("runner_cheap")

    return score, reasons


def _score_model_fit(
    *,
    step: str,
    model_name: str,
    model_strengths: tuple[str, ...],
    hints: dict[str, str],
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 15

    strengths = set(model_strengths)
    wide_edit_surface = hints.get("edit_surface", "").lower() in {"wide", "large"}
    complex_parsing = hints.get("complex_parsing", "").lower() in {"true", "yes", "1"}

    if step in {"compile-tasks", "route explain"} or step.startswith("docs/"):
        if model_name in {"haiku-4.5", "gpt-5.1-mini"}:
            score += 16
            reasons.append("cheap_model_preferred")
    elif step == "run-task":
        if model_name == "sonnet-4.55":
            score += 20
            reasons.append("preferred_code_edit_model")
        if wide_edit_surface and model_name == "gpt-5.3-codex":
            score += 20
            reasons.append("wide_edit_surface")
        if "tests" in strengths:
            score += 8
            reasons.append("tests")
    elif step == "collect-evidence":
        if model_name == "gpt-5.1-mini":
            score += 14
            reasons.append("cheap_evidence_model")
        if complex_parsing and model_name in {"sonnet-4.55", "gpt-5.2"}:
            score += 12
            reasons.append("complex_parsing")
    elif step in {"gate-allowlist", "commit-run", "finish"} and model_name == "gpt-5.2":
        score += 22
        reasons.append("correctness_pressure")

    if "balanced" in strengths:
        score += 4
        reasons.append("balanced")

    return score, reasons


def _cost_penalty(*, step: str, cost_tier: str) -> int:
    if step in {"compile-tasks", "collect-evidence", "route explain"} or step.startswith("docs/"):
        penalties = {"cheap": 0, "medium": -8, "high": -16}
    elif step == "run-task":
        penalties = {"cheap": -8, "medium": -2, "high": -6}
    elif step in {"gate-allowlist", "commit-run", "finish"}:
        penalties = {"cheap": -4, "medium": 0, "high": -4}
    else:
        penalties = {"cheap": 0, "medium": -2, "high": -6}
    return penalties[cost_tier]


def _confidence_penalty(*, step: str, model_name: str) -> int:
    if step == "run-task" and model_name == "gpt-5.1-mini":
        return -10
    if step in {"gate-allowlist", "commit-run", "finish"} and model_name in {"haiku-4.5", "gpt-5.1-mini"}:
        return -8
    return 0
