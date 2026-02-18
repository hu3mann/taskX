"""Deterministic artifact writer for orchestrator runs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from taskx.artifacts.canonical_json import sha256_file, write_json

if TYPE_CHECKING:
    from pathlib import Path

ARTIFACT_INDEX_SCHEMA_VERSION = "taskx.orchestrator.v0"


def write_run_artifacts(
    run_dir: Path,
    *,
    route_plan: dict[str, Any],
    report: dict[str, Any],
    stdout_text: str | None,
    stderr_text: str | None,
) -> dict[str, Any]:
    """Write deterministic orchestrator artifacts and return the index payload."""
    run_dir.mkdir(parents=True, exist_ok=True)

    route_plan_path = run_dir / "ROUTE_PLAN.json"
    write_json(route_plan_path, route_plan)

    report_status = str(report.get("status", "")).strip().lower()
    report_filename = "REFUSAL_REPORT.json" if report_status == "refused" else "RUN_REPORT.json"
    report_path = run_dir / report_filename
    write_json(report_path, report)

    artifacts: list[tuple[str, Path]] = [
        ("ROUTE_PLAN.json", route_plan_path),
        (report_filename, report_path),
    ]

    if stdout_text is not None:
        stdout_path = run_dir / "STDOUT.log"
        stdout_path.write_text(stdout_text, encoding="utf-8")
        artifacts.append(("STDOUT.log", stdout_path))

    if stderr_text is not None:
        stderr_path = run_dir / "STDERR.log"
        stderr_path.write_text(stderr_text, encoding="utf-8")
        artifacts.append(("STDERR.log", stderr_path))

    index_payload: dict[str, Any] = {
        "schema_version": ARTIFACT_INDEX_SCHEMA_VERSION,
        "artifacts": [
            {
                "name": artifact_name,
                "path": artifact_name,
                "sha256": sha256_file(artifact_path),
            }
            for artifact_name, artifact_path in artifacts
        ],
    }
    write_json(run_dir / "ARTIFACT_INDEX.json", index_payload)
    return index_payload
