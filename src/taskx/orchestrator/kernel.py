"""TaskX orchestrator v0 kernel."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from taskx.artifacts import canonical_dumps, sha256_text, write_run_artifacts
from taskx.orchestrator.handoff import build_handoff_chunks, render_handoff_chunks
from taskx.router import build_route_plan, route_plan_to_dict
from taskx.router.availability import availability_path_for_repo, default_route_policy
from taskx.runners import RUNNER_ADAPTERS
from taskx.utils.repo import find_taskx_repo_root


def orchestrate(packet_path: str) -> dict[str, Any]:
    """
    Orchestrate one deterministic TaskX run.

    Returns an outcome with:
      - status: "ok" | "refused" | "error" | "needs_handoff"
      - run_dir: str
      - artifacts: dict (from ARTIFACT_INDEX)
    """
    packet_file = Path(packet_path).expanduser().resolve()
    repo_root = find_taskx_repo_root(packet_file.parent) or Path.cwd().resolve()

    try:
        raw_packet = _read_packet_text(packet_file)
    except OSError as exc:
        packet_sha16 = sha256_text(str(packet_file))[:16]
        run_dir = _deterministic_run_dir(
            repo_root=repo_root,
            task_id=_normalize_task_id(packet_file.stem),
            packet_sha16=packet_sha16,
        )
        route_plan = _packet_refusal_route_plan(
            repo_root=repo_root,
            packet_path=packet_file,
            reason=f"Packet read error: {exc}",
        )
        route_plan["run_dir"] = str(run_dir)
        route_plan["handoff_chunks"] = build_handoff_chunks({}, route_plan)
        report = {
            "status": "refused",
            "reason_code": "PACKET_READ_ERROR",
            "message": "Packet could not be read",
            "reasons": [f"Packet read error: {exc}"],
        }
        artifacts = write_run_artifacts(
            run_dir,
            route_plan=route_plan,
            report=report,
            stdout_text=None,
            stderr_text=None,
        )
        return {
            "status": "refused",
            "run_dir": str(run_dir),
            "artifacts": artifacts,
            "reason": "PACKET_READ_ERROR",
        }

    packet, packet_error = _parse_packet_json(raw_packet)

    if packet is None:
        packet_sha16 = sha256_text(raw_packet)[:16]
        run_dir = _deterministic_run_dir(
            repo_root=repo_root,
            task_id=_normalize_task_id(packet_file.stem),
            packet_sha16=packet_sha16,
        )
        route_plan = _packet_refusal_route_plan(
            repo_root=repo_root,
            packet_path=packet_file,
            reason=f"Invalid packet JSON: {packet_error}",
        )
        route_plan["run_dir"] = str(run_dir)
        route_plan["handoff_chunks"] = build_handoff_chunks({}, route_plan)
        report = {
            "status": "refused",
            "reason_code": "INVALID_PACKET_JSON",
            "message": "Packet must be valid JSON",
            "reasons": [f"Invalid packet JSON: {packet_error}"],
        }
        artifacts = write_run_artifacts(
            run_dir,
            route_plan=route_plan,
            report=report,
            stdout_text=None,
            stderr_text=None,
        )
        return {
            "status": "refused",
            "run_dir": str(run_dir),
            "artifacts": artifacts,
            "reason": "INVALID_PACKET_JSON",
        }

    packet_sha16 = sha256_text(canonical_dumps(packet))[:16]
    task_id = _normalize_task_id(_packet_task_id(packet, fallback=packet_file.stem))

    planned = build_route_plan(
        repo_root=repo_root,
        packet_path=packet_file,
        steps=_packet_steps(packet),
    )
    route_plan = route_plan_to_dict(planned)

    run_dir = _deterministic_run_dir(repo_root=repo_root, task_id=task_id, packet_sha16=packet_sha16)
    route_plan["run_dir"] = str(run_dir)
    route_plan["handoff_chunks"] = build_handoff_chunks(packet, route_plan)

    if route_plan.get("status") == "refused":
        reasons = _normalize_reasons(route_plan.get("refusal_reasons", []))
        report = {
            "status": "refused",
            "reason_code": "ROUTE_REFUSED",
            "message": "Route plan refused",
            "reasons": reasons,
        }
        artifacts = write_run_artifacts(
            run_dir,
            route_plan=route_plan,
            report=report,
            stdout_text=None,
            stderr_text=None,
        )
        return {
            "status": "refused",
            "run_dir": str(run_dir),
            "artifacts": artifacts,
            "reason": reasons[0] if reasons else "Route plan refused",
        }

    execution_mode = str(packet.get("execution_mode", "auto")).strip().lower() or "auto"
    if execution_mode not in {"auto", "manual"}:
        report = {
            "status": "refused",
            "reason_code": "INVALID_EXECUTION_MODE",
            "message": f"Unsupported execution_mode: {execution_mode}",
            "reasons": [f"Unsupported execution_mode: {execution_mode}"],
        }
        artifacts = write_run_artifacts(
            run_dir,
            route_plan=route_plan,
            report=report,
            stdout_text=None,
            stderr_text=None,
        )
        return {
            "status": "refused",
            "run_dir": str(run_dir),
            "artifacts": artifacts,
            "reason": "INVALID_EXECUTION_MODE",
        }

    if execution_mode == "manual":
        next_step = _first_incomplete_step(route_plan, run_dir)
        if next_step is not None:
            chunks = route_plan.get("handoff_chunks", [])
            handoff_stdout = render_handoff_chunks(chunks)
            report = {
                "status": "needs_handoff",
                "next_step": next_step,
                "message": "Manual handoff required",
                "handoff_chunks_sha256": sha256_text(canonical_dumps(chunks)),
            }
            artifacts = write_run_artifacts(
                run_dir,
                route_plan=route_plan,
                report=report,
                stdout_text=handoff_stdout,
                stderr_text=None,
            )
            return {
                "status": "needs_handoff",
                "run_dir": str(run_dir),
                "artifacts": artifacts,
                "stdout_text": handoff_stdout,
            }

        report = {
            "status": "ok",
            "message": "Manual handoff complete",
            "runner_id": None,  # type: ignore[dict-item]
            "model_id": None,  # type: ignore[dict-item]
            "step": None,  # type: ignore[dict-item]
            "outputs": [],
        }
        artifacts = write_run_artifacts(
            run_dir,
            route_plan=route_plan,
            report=report,
            stdout_text=None,
            stderr_text=None,
        )
        return {"status": "ok", "run_dir": str(run_dir), "artifacts": artifacts}

    selected_step = _select_single_step(route_plan)
    if selected_step is None:
        report = {
            "status": "refused",
            "reason_code": "NO_RUNNER_SELECTED",
            "message": "No runnable step selected",
            "reasons": ["No runnable step selected"],
        }
        artifacts = write_run_artifacts(
            run_dir,
            route_plan=route_plan,
            report=report,
            stdout_text=None,
            stderr_text=None,
        )
        return {
            "status": "refused",
            "run_dir": str(run_dir),
            "artifacts": artifacts,
            "reason": "NO_RUNNER_SELECTED",
        }

    runner_id = str(selected_step["runner"])
    adapter_cls = RUNNER_ADAPTERS.get(runner_id)
    if adapter_cls is None:
        report = {
            "status": "refused",
            "reason_code": "UNKNOWN_RUNNER",
            "message": f"Unknown runner: {runner_id}",
            "reasons": [f"Unknown runner: {runner_id}"],
            "runner_id": runner_id,  # type: ignore[dict-item]
            "model_id": selected_step.get("model"),  # type: ignore[dict-item]
            "step": selected_step.get("step"),  # type: ignore[dict-item]
        }
        artifacts = write_run_artifacts(
            run_dir,
            route_plan=route_plan,
            report=report,
            stdout_text=None,
            stderr_text=None,
        )
        return {
            "status": "refused",
            "run_dir": str(run_dir),
            "artifacts": artifacts,
            "reason": "UNKNOWN_RUNNER",
        }

    adapter = adapter_cls()
    runspec = adapter.prepare(packet, {"steps": [selected_step], "route_plan": route_plan})
    result = adapter.run(runspec)
    normalized = adapter.normalize(result)

    status = str(normalized.get("status", "error")).strip().lower() or "error"
    if status not in {"ok", "error", "refused"}:
        status = "error"

    report = {
        "status": status,
        "runner_id": normalized.get("runner_id", runner_id),  # type: ignore[dict-item]
        "model_id": normalized.get("model_id", selected_step.get("model")),  # type: ignore[dict-item]
        "step": normalized.get("step", selected_step.get("step")),  # type: ignore[dict-item]
        "reason_code": normalized.get("reason_code"),  # type: ignore[dict-item]
        "outputs": list(normalized.get("outputs", [])),
    }

    stdout_text = _optional_text(result.get("stdout_text"))
    stderr_text = _optional_text(result.get("stderr_text"))
    artifacts = write_run_artifacts(
        run_dir,
        route_plan=route_plan,
        report=report,
        stdout_text=stdout_text,
        stderr_text=stderr_text,
    )
    outcome: dict[str, Any] = {
        "status": status,
        "run_dir": str(run_dir),
        "artifacts": artifacts,
    }
    if status == "refused" and report.get("reason_code"):
        outcome["reason"] = report["reason_code"]
    return outcome


def _read_packet_text(packet_path: Path) -> str:
    return packet_path.read_text(encoding="utf-8")


def _parse_packet_json(raw_packet: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(raw_packet)
    except json.JSONDecodeError as exc:
        return None, str(exc)

    if not isinstance(payload, dict):
        return None, "top-level packet payload must be a JSON object"
    return payload, None


def _deterministic_run_dir(*, repo_root: Path, task_id: str, packet_sha16: str) -> Path:
    return (repo_root / "out" / "runs" / task_id / packet_sha16).resolve()


def _packet_task_id(packet: dict[str, Any], *, fallback: str) -> str:
    for key in ("task_id", "taskId", "id", "packet_id", "name"):
        value = packet.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return fallback


def _packet_steps(packet: dict[str, Any]) -> tuple[str, ...] | None:
    raw_steps = packet.get("steps")
    if raw_steps is None:
        return None

    parsed: list[str] = []
    if isinstance(raw_steps, str):
        candidates: list[Any] = [raw_steps]
    elif isinstance(raw_steps, list):
        candidates = raw_steps
    else:
        return None

    for item in candidates:
        if not isinstance(item, str):
            continue
        for value in item.split(","):
            step = value.strip()
            if step:
                parsed.append(step)

    return tuple(parsed) if parsed else None


def _normalize_task_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "task"


def _packet_refusal_route_plan(*, repo_root: Path, packet_path: Path, reason: str) -> dict[str, Any]:
    policy = default_route_policy()
    return {
        "status": "refused",
        "repo_root": str(repo_root),
        "packet_path": str(packet_path),
        "availability_path": str(availability_path_for_repo(repo_root)),
        "policy": {
            "require_explain": policy.require_explain,
            "stop_on_ambiguity": policy.stop_on_ambiguity,
            "max_cost_tier": policy.max_cost_tier,
            "escalation_ladder": list(policy.escalation_ladder),
            "max_escalations": policy.max_escalations,
            "min_total_score": policy.min_total_score,
        },
        "refusal_reasons": [reason],
        "steps": [],
    }


def _normalize_reasons(reasons: list[Any]) -> list[str]:
    normalized: list[str] = []
    for item in reasons:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, dict) and "message" in item:
            normalized.append(str(item["message"]))
        else:
            normalized.append(str(item))
    return normalized


def _select_single_step(route_plan: dict[str, Any]) -> dict[str, Any] | None:
    for step in route_plan.get("steps", []):
        if not isinstance(step, dict):
            continue
        if step.get("runner") and step.get("model"):
            return step
    return None


def _first_incomplete_step(route_plan: dict[str, Any], run_dir: Path) -> str | None:
    for step in route_plan.get("steps", []):
        if not isinstance(step, dict):
            continue
        step_name = str(step.get("step", "")).strip()
        if not step_name:
            continue
        sentinel = run_dir / f"STEP_{_normalize_step_token(step_name)}.DONE"
        if not sentinel.exists():
            return step_name
    return None


def _normalize_step_token(step: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", step.strip().upper())
    return normalized.strip("_") or "STEP"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
