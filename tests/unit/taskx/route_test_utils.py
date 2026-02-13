"""Helpers for router CLI tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import yaml

from taskx.router.availability import AVAILABILITY_CONFIG_TEMPLATE


def create_taskx_repo(repo_root: Path, project_id: str = "taskx.core") -> Path:
    """Initialize a minimal TaskX repo directory with identity rails."""
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / ".taskxroot").write_text("", encoding="utf-8")
    project_identity = repo_root / ".taskx" / "project.json"
    project_identity.parent.mkdir(parents=True, exist_ok=True)
    project_identity.write_text(
        json.dumps({"project_id": project_id, "packet_required_header": False}, sort_keys=True),
        encoding="utf-8",
    )
    return repo_root


def write_packet(
    repo_root: Path,
    *,
    name: str = "PACKET.md",
    contents: str | None = None,
) -> Path:
    """Create a simple packet file."""
    packet_path = repo_root / name
    contents = contents or "# Packet\nROUTER_HINTS:\n  risk: low\n"
    packet_path.write_text(contents, encoding="utf-8")
    return packet_path


def build_availability_config(
    *,
    policy_overrides: dict[str, Any] | None = None,
    models: dict[str, Any] | None = None,
    runners: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a route availability config derived from the template."""
    template = deepcopy(AVAILABILITY_CONFIG_TEMPLATE)
    if models is not None:
        template["models"] = models
    if runners is not None:
        template["runners"] = runners
    if policy_overrides:
        template["policy"].update(policy_overrides)
    return template


def write_availability(
    repo_root: Path,
    *,
    policy_overrides: dict[str, Any] | None = None,
    models: dict[str, Any] | None = None,
    runners: dict[str, Any] | None = None,
) -> Path:
    """Write availability.yaml under .taskx/runtime."""
    config = build_availability_config(
        policy_overrides=policy_overrides,
        models=models,
        runners=runners,
    )
    runtime_path = repo_root / ".taskx" / "runtime"
    runtime_path.mkdir(parents=True, exist_ok=True)
    availability_path = runtime_path / "availability.yaml"
    availability_path.write_text(yaml.safe_dump(config, sort_keys=True), encoding="utf-8")
    return availability_path


def read_route_plan(repo_root: Path) -> dict[str, Any]:
    """Load the most recent route plan JSON artifact."""
    plan_path = repo_root / "out" / "taskx_route" / "ROUTE_PLAN.json"
    return json.loads(plan_path.read_text(encoding="utf-8"))


def tail_lines(contents: str, count: int = 5) -> list[str]:
    """Utility to read the last N lines of a multi-line string."""
    return contents.strip().splitlines()[-count:]


def ordered_steps(steps: Iterable[dict[str, Any]]) -> list[str]:
    """Return the step names in iteration order."""
    return [step["step"] for step in steps]
