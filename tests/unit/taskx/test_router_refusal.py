"""Refusal contract tests for TaskX route planning."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from taskx.cli import cli

if TYPE_CHECKING:
    from pathlib import Path


def test_route_plan_refuses_when_no_runners_available(tmp_path: Path, monkeypatch) -> None:
    """Planner should return exit code 2 and write refused artifacts."""
    runner = CliRunner()
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    packet = repo / "PACKET.md"
    packet.write_text("# Packet\n", encoding="utf-8")

    availability_path = repo / ".taskx" / "runtime" / "availability.yaml"
    availability_path.parent.mkdir(parents=True, exist_ok=True)
    availability_path.write_text(
        """
models:
  gpt-5.1-mini:
    strengths: [cheap]
    cost_tier: cheap
    context: medium
runners:
  claude_code:
    available: false
    strengths: [code_edit]
policy:
  require_explain: true
  stop_on_ambiguity: true
  max_cost_tier: high
  escalation_ladder: [gpt-5.1-mini]
  max_escalations: 1
  min_total_score: 50
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.chdir(repo)

    result = runner.invoke(cli, ["route", "plan", "--repo-root", str(repo), "--packet", str(packet)])
    assert result.exit_code == 2

    plan_path = repo / "out" / "taskx_route" / "ROUTE_PLAN.json"
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    assert payload["status"] == "refused"
    assert payload["refusal_reasons"]
