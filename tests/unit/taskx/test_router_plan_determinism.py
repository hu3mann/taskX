"""Determinism coverage for TaskX route planning."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from taskx.cli import cli

if TYPE_CHECKING:
    from pathlib import Path


def test_route_plan_is_deterministic_for_same_inputs(tmp_path: Path, monkeypatch) -> None:
    """Same packet + availability must produce byte-identical plan JSON."""
    runner = CliRunner()
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    packet = repo / "PACKET.md"
    packet.write_text(
        "# Packet\n"
        "ROUTER_HINTS:\n"
        "  risk: low\n"
        "  edit_surface: medium\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo)

    init_result = runner.invoke(cli, ["route", "init", "--repo-root", str(repo)])
    assert init_result.exit_code == 0, init_result.output

    first = runner.invoke(cli, ["route", "plan", "--repo-root", str(repo), "--packet", str(packet)])
    assert first.exit_code == 0, first.output

    plan_path = repo / "out" / "taskx_route" / "ROUTE_PLAN.json"
    first_bytes = plan_path.read_bytes()

    second = runner.invoke(cli, ["route", "plan", "--repo-root", str(repo), "--packet", str(packet)])
    assert second.exit_code == 0, second.output

    second_bytes = plan_path.read_bytes()
    assert second_bytes == first_bytes
