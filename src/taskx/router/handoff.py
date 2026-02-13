"""Handoff renderer for assisted routing plans."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from taskx.router.types import RoutePlan


def render_handoff_markdown(plan: RoutePlan) -> str:
    """Render copy/paste runner handoff instructions for each plan step."""
    lines: list[str] = [
        "# HANDOFF",
        "",
        f"- status: {plan.status}",
        f"- repo_root: {plan.repo_root}",
        f"- packet_path: {plan.packet_path}",
        "",
    ]

    if plan.refusal_reasons:
        lines.extend(["## Refusal Reasons", ""])
        for reason in plan.refusal_reasons:
            lines.append(f"- {reason}")
        lines.append("")

    lines.extend(["## Runner Command Stubs", ""])
    lines.extend(
        [
            "### Codex Desktop prompt",
            "",
            "```text",
            _codex_prompt("<step>", "<model>"),
            "```",
            "",
            "### Claude Code prompt",
            "",
            "```text",
            _claude_prompt("<step>", "<model>"),
            "```",
            "",
            "### Copilot CLI command",
            "",
            "```bash",
            _copilot_command("<step>", "<model>"),
            "```",
            "",
        ]
    )

    for step in plan.steps:
        lines.extend(
            [
                f"## Step: {step.step}",
                "",
                f"- runner: {step.runner or 'none'}",
                f"- model: {step.model or 'none'}",
                f"- confidence: {step.confidence:.2f}",
                "",
            ]
        )

        if step.runner == "codex_desktop":
            lines.extend(
                [
                    "### Codex Desktop prompt",
                    "",
                    "```text",
                    _codex_prompt(step.step, step.model),
                    "```",
                    "",
                ]
            )
        elif step.runner == "claude_code":
            lines.extend(
                [
                    "### Claude Code prompt",
                    "",
                    "```text",
                    _claude_prompt(step.step, step.model),
                    "```",
                    "",
                ]
            )
        elif step.runner == "copilot_cli":
            lines.extend(
                [
                    "### Copilot CLI command",
                    "",
                    "```bash",
                    _copilot_command(step.step, step.model),
                    "```",
                    "",
                ]
            )
        else:
            lines.extend(["No runner available for this step.", ""])

        lines.extend(
            [
                "### Artifact expectations",
                "",
                "- Update route artifacts under `out/taskx_route/`.",
                "- Preserve deterministic outputs for identical inputs.",
                "",
            ]
        )

    return "\n".join(lines)


def _codex_prompt(step: str, model: str | None) -> str:
    selected_model = model or "unspecified"
    return (
        f"Model: {selected_model}\n"
        f"Execute TaskX step `{step}` in assisted mode.\n"
        "Do not run external runners. Produce deterministic artifacts only."
    )


def _claude_prompt(step: str, model: str | None) -> str:
    selected_model = model or "unspecified"
    return (
        f"Model: {selected_model}\n"
        f"Implement TaskX step `{step}` using the packet instructions.\n"
        "Print commands/prompts only for handoff, no background execution."
    )


def _copilot_command(step: str, model: str | None) -> str:
    selected_model = model or "unspecified"
    return (
        "copilot chat "
        f"\"Model={selected_model}; execute step={step}; assisted mode only; no external invocation\""
    )
