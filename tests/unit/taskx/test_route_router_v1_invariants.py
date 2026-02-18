"""Deterministic invariants for Router v1 assisted flow."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from taskx.router.availability import AVAILABILITY_CONFIG_TEMPLATE

DEFAULT_LADDER = AVAILABILITY_CONFIG_TEMPLATE["policy"]["escalation_ladder"]

REFUSAL_STEPS = ["alpha", "beta"]


def _bootstrap_identity(repo_root: Path) -> None:
    taskx_dir = repo_root / ".taskx"
    taskx_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / ".taskxroot").write_text("", encoding="utf-8")
    (taskx_dir / "project.json").write_text(
        json.dumps({"project_id": "taskx.core"}, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_packet(repo_root: Path, text: str = "# Packet\n") -> Path:
    packet = repo_root / "PACKET.md"
    packet.write_text(text, encoding="utf-8")
    return packet


def _run(repo_root: Path, args: list[str], expect: int | None = None) -> CompletedProcess:
    result = subprocess.run(
        ["taskx", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if expect is not None:
        assert result.returncode == expect, result.stdout + result.stderr
    return result


def _init_route(repo_root: Path) -> CompletedProcess:
    return _run(repo_root, ["route", "init", "--repo-root", str(repo_root)], expect=0)


def _load_plan(repo_root: Path) -> dict:
    plan_path = repo_root / "out" / "taskx_route" / "ROUTE_PLAN.json"
    return json.loads(plan_path.read_text(encoding="utf-8"))


def _ensure_plan_artifacts(repo_root: Path, *, require: bool = True) -> None:
    plan_path = repo_root / "out" / "taskx_route" / "ROUTE_PLAN.json"
    md_path = repo_root / "out" / "taskx_route" / "ROUTE_PLAN.md"
    if require:
        assert plan_path.exists()
        assert md_path.exists()
    else:
        if not (plan_path.exists() and md_path.exists()):
            return


def _run_route_plan(repo_root: Path) -> CompletedProcess:
    return _run(
        repo_root,
        [
            "route",
            "plan",
            "--repo-root",
            str(repo_root),
            "--packet",
            str(repo_root / "PACKET.md"),
            "--steps",
            ",".join(REFUSAL_STEPS),
        ],
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _bootstrap_identity(repo_root)
    _write_packet(repo_root)
    return repo_root


def test_route_plan_refusal_writes_artifacts_and_is_deterministic(repo: Path) -> None:
    _init_route(repo)

    first = _run_route_plan(repo)
    assert first.returncode == 2
    _ensure_plan_artifacts(repo)
    plan1 = _load_plan(repo)

    assert plan1["status"] == "refused"
    assert plan1["policy"]["escalation_ladder"] == DEFAULT_LADDER
    assert len(plan1["refusal_reasons"]) == len(REFUSAL_STEPS)
    for index, step in enumerate(REFUSAL_STEPS):
        assert f"Step `{step}` below score threshold" in plan1["refusal_reasons"][index]["message"]
        assert plan1["steps"][index]["step"] == step
        candidates = plan1["steps"][index]["candidates_top3"]
        assert isinstance(candidates, list)
        assert candidates
        top_candidate = candidates[0]
        for key in ("model", "runner", "total"):
            assert key in top_candidate
    for step in plan1["steps"]:
        assert step["step"] in REFUSAL_STEPS

    second = _run_route_plan(repo)
    assert second.returncode == 2
    plan2 = _load_plan(repo)
    assert json.dumps(plan1, sort_keys=True) == json.dumps(plan2, sort_keys=True)


def test_route_plan_preserves_declared_ladder_order(repo: Path) -> None:
    _init_route(repo)
    availability_path = repo / ".taskx" / "runtime" / "availability.yaml"
    assert availability_path.exists()
    text = availability_path.read_text()
    ladder_section = "escalation_ladder"
    assert ladder_section in text
    new_ladder = ["sonnet-4.55", "gpt-5.3-codex", "haiku-4.5"]
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if ladder_section in line) + 1
    end = start
    while end < len(lines) and lines[end].strip().startswith("-"):
        end += 1
    lines[start:end] = [f"    - \"{model}\"" for model in new_ladder]
    availability_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _run_route_plan(repo)
    assert result.returncode == 2
    _ensure_plan_artifacts(repo)
    plan = _load_plan(repo)
    assert plan["policy"]["escalation_ladder"] == new_ladder


def test_route_plan_missing_availability_refuses_and_writes_plan(repo: Path) -> None:
    _init_route(repo)
    availability_path = repo / ".taskx" / "runtime" / "availability.yaml"
    assert availability_path.exists()
    availability_path.unlink()

    result = _run_route_plan(repo)
    assert result.returncode == 2
    _ensure_plan_artifacts(repo)
    plan = _load_plan(repo)
    assert plan["status"] == "refused"
    assert any("availability" in reason["message"] and "missing" in reason["message"] for reason in plan["refusal_reasons"])


def test_route_plan_invalid_availability_refuses_and_writes_plan(repo: Path) -> None:
    _init_route(repo)
    availability_path = repo / ".taskx" / "runtime" / "availability.yaml"
    availability_path.write_text(":- not yaml\n", encoding="utf-8")

    result = _run_route_plan(repo)
    assert result.returncode == 2
    _ensure_plan_artifacts(repo)
    plan = _load_plan(repo)
    assert plan["status"] == "refused"
    assert any("YAML" in reason["message"] or "parse" in reason["message"] for reason in plan["refusal_reasons"])


def test_route_plan_availability_missing_required_keys_refuses_and_writes_plan(repo: Path) -> None:
    _init_route(repo)
    availability_path = repo / ".taskx" / "runtime" / "availability.yaml"
    availability_path.write_text("models:\n", encoding="utf-8")

    result = _run_route_plan(repo)
    assert result.returncode == 2
    _ensure_plan_artifacts(repo)
    plan = _load_plan(repo)
    assert plan["status"] == "refused"
    assert any("missing" in reason["message"] and "model" in reason["message"].lower() for reason in plan["refusal_reasons"])


def test_route_handoff_and_explain_are_deterministic(repo: Path) -> None:
    _init_route(repo)
    plan_result = _run_route_plan(repo)
    assert plan_result.returncode == 2
    _ensure_plan_artifacts(repo)
    plan_path = repo / "out" / "taskx_route" / "ROUTE_PLAN.json"

    def handoff_stdout() -> str:
        process = _run(
            repo,
            [
                "route",
                "handoff",
                "--repo-root",
                str(repo),
                "--packet",
                str(repo / "PACKET.md"),
                "--plan",
                str(plan_path),
            ],
        )
        assert process.returncode == 0
        return process.stdout

    handoff1 = handoff_stdout()
    handoff2 = handoff_stdout()
    assert handoff1 == handoff2
    assert str(repo / "PACKET.md") in handoff1
    assert handoff1.index("alpha") < handoff1.index("beta")

    def explain_stdout() -> str:
        process = _run(
            repo,
            [
                "route",
                "explain",
                "--repo-root",
                str(repo),
                "--packet",
                str(repo / "PACKET.md"),
                "--plan",
                str(plan_path),
                "--step",
                "alpha",
            ],
        )
        assert process.returncode == 0
        return process.stdout

    explain1 = explain_stdout()
    explain2 = explain_stdout()
    assert explain1 == explain2
    assert "alpha" in explain1
