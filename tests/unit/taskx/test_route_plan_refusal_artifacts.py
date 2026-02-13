"""Deterministic route invariants (plan refusals, availability contracts, explain/hand off)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from taskx.cli import cli
from taskx.router.types import DEFAULT_STEPS
from tests.unit.taskx.route_test_utils import (
    create_taskx_repo,
    ordered_steps,
    read_route_plan,
    write_availability,
    write_packet,
)

DEFAULT_ESCALATION_LADDER = ["gpt-5.1-mini", "haiku-4.5", "sonnet-4.55", "gpt-5.3-codex"]


def test_route_plan_refusal_writes_expected_artifacts(tmp_path: Path) -> None:
    repo = create_taskx_repo(tmp_path / "refusal")
    packet = write_packet(repo)
    write_availability(repo, policy_overrides={"min_total_score": 999})

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "route",
            "plan",
            "--repo-root",
            str(repo),
            "--packet",
            str(packet),
            "--steps",
            "alpha,beta",
        ],
    )
    assert result.exit_code == 2, result.output

    plan = read_route_plan(repo)
    assert plan["status"] == "refused"
    assert plan["packet_path"].endswith("PACKET.md")
    assert plan["policy"]["escalation_ladder"] == DEFAULT_ESCALATION_LADDER

    refusal_reasons = plan["refusal_reasons"]
    assert len(refusal_reasons) == 2
    assert refusal_reasons[0].startswith("Step `alpha` below score threshold:")
    assert refusal_reasons[1].startswith("Step `beta` below score threshold:")

    assert ordered_steps(plan["steps"]) == ["alpha", "beta"]
    for step in plan["steps"]:
        candidates = step["candidates_top3"]
        assert candidates, "Expected at least one candidate per step"
        assert set(candidates[0].keys()) == {"runner", "model", "total"}


def test_escalation_ladder_order_respects_declaration(tmp_path: Path) -> None:
    repo = create_taskx_repo(tmp_path / "ladder")
    packet = write_packet(repo)
    custom_ladder = ["sonnet-4.55", "gpt-5.3-codex", "haiku-4.5"]
    write_availability(repo, policy_overrides={"escalation_ladder": custom_ladder, "min_total_score": 10})

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["route", "plan", "--repo-root", str(repo), "--packet", str(packet)],
    )
    assert result.exit_code == 0, result.output

    plan = read_route_plan(repo)
    assert plan["policy"]["escalation_ladder"] == custom_ladder


def test_route_plan_refuses_when_availability_missing(tmp_path: Path) -> None:
    repo = create_taskx_repo(tmp_path / "missing")
    packet = write_packet(repo)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["route", "plan", "--repo-root", str(repo), "--packet", str(packet)],
    )
    plan_path = repo / "out" / "taskx_route" / "ROUTE_PLAN.json"
    plan_md_path = repo / "out" / "taskx_route" / "ROUTE_PLAN.md"
    assert result.exit_code == 2, result.output
    assert plan_path.exists()
    assert plan_md_path.exists()
    plan = read_route_plan(repo)
    assert plan["status"] == "refused"
    assert plan["policy"]["escalation_ladder"] == DEFAULT_ESCALATION_LADDER
    assert ordered_steps(plan["steps"]) == list(DEFAULT_STEPS)
    reason = plan["refusal_reasons"][0]
    assert "Missing availability config" in reason
    assert "availability" in reason.lower()
    assert "missing" in reason.lower()
    assert "Missing availability config at" in result.output


def test_route_plan_refuses_on_invalid_availability_yaml(tmp_path: Path) -> None:
    repo = create_taskx_repo(tmp_path / "invalid_yaml")
    packet = write_packet(repo)
    runtime = repo / ".taskx" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "availability.yaml").write_text("models: [broken", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["route", "plan", "--repo-root", str(repo), "--packet", str(packet)],
    )
    assert result.exit_code == 2, result.output
    assert "availability.yaml parse error:" in result.output


def test_route_plan_refuses_on_missing_api_keys(tmp_path: Path) -> None:
    repo = create_taskx_repo(tmp_path / "missing_fields")
    packet = write_packet(repo)
    runtime = repo / ".taskx" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    runtime.joinpath("availability.yaml").write_text(
        "models: {}\nrunners: {}\npolicy: {}\n", encoding="utf-8"
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["route", "plan", "--repo-root", str(repo), "--packet", str(packet)],
    )
    assert result.exit_code == 2, result.output
    assert "availability.yaml missing required non-empty `models` mapping" in result.output


def test_route_handoff_reports_step_order_and_packet(tmp_path: Path) -> None:
    repo = create_taskx_repo(tmp_path / "handoff")
    packet = write_packet(repo)
    write_availability(repo, policy_overrides={"min_total_score": 20})

    runner = CliRunner()
    plan_result = runner.invoke(
        cli,
        [
            "route",
            "plan",
            "--repo-root",
            str(repo),
            "--packet",
            str(packet),
            "--steps",
            "alpha,beta",
        ],
    )
    assert plan_result.exit_code == 0, plan_result.output

    plan_path = repo / "out" / "taskx_route" / "ROUTE_PLAN.json"
    handoff_result = runner.invoke(
        cli,
        [
            "route",
            "handoff",
            "--repo-root",
            str(repo),
            "--packet",
            str(packet),
            "--plan",
            str(plan_path),
        ],
    )
    assert handoff_result.exit_code == 0, handoff_result.output

    contents = (repo / "out" / "taskx_route" / "HANDOFF.md").read_text(encoding="utf-8")
    assert f"- packet_path: {packet}" in contents
    assert contents.index("## Step: alpha") < contents.index("## Step: beta")
    assert "Model: sonnet-4.55" in contents


def test_route_explain_is_reproducible(tmp_path: Path) -> None:
    repo = create_taskx_repo(tmp_path / "explain")
    packet = write_packet(repo)
    write_availability(repo, policy_overrides={"min_total_score": 20})

    runner = CliRunner()
    runner.invoke(
        cli,
        [
            "route",
            "plan",
            "--repo-root",
            str(repo),
            "--packet",
            str(packet),
            "--steps",
            "alpha,beta",
        ],
    )
    plan_path = repo / "out" / "taskx_route" / "ROUTE_PLAN.json"

    first = runner.invoke(
        cli,
        [
            "route",
            "explain",
            "--repo-root",
            str(repo),
            "--plan",
            str(plan_path),
            "--step",
            "alpha",
        ],
    )
    second = runner.invoke(
        cli,
        [
            "route",
            "explain",
            "--repo-root",
            str(repo),
            "--plan",
            str(plan_path),
            "--step",
            "alpha",
        ],
    )
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert first.output == second.output
