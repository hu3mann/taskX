"""Spec feedback loop implementation - deterministic, no-LLM."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from taskx.pipeline.spec_feedback.types import Evidence, Patch
from taskx.schemas.validator import validate_data
from taskx.utils.json_output import write_json_strict

CHATX_VERSION = "0.1.0"


def generate_feedback(
    run_paths: list[Path],
    task_queue_path: Path,
    output_dir: Path,
    conflict_ledger_path: Path | None = None,
    timestamp_mode: str = "deterministic",
    max_runs: int = 200,
) -> None:
    """Generate feedback artifacts from run summaries.

    Args:
        run_paths: List of run directories containing RUN_SUMMARY.json
        task_queue_path: Path to TASK_QUEUE.json
        output_dir: Output directory for feedback artifacts
        conflict_ledger_path: Optional path to conflict ledger
        timestamp_mode: "deterministic" or "wallclock"
        max_runs: Maximum number of runs to process
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load and validate task queue
    with open(task_queue_path) as f:
        task_queue = json.load(f)
    ok, errors = validate_data(task_queue, "task_queue", strict=True)
    if not ok:
        raise ValueError(f"Invalid task queue: {errors}")

    # Load and validate run summaries
    run_summaries = _load_run_summaries(run_paths, max_runs)

    # Generate patches
    patches = _generate_patches(run_summaries, task_queue)

    # Compute input hash
    input_hash = _compute_input_hash(task_queue_path, run_summaries)

    # Generate timestamp
    generated_at = (
        "1970-01-01T00:00:00Z"
        if timestamp_mode == "deterministic"
        else datetime.now(UTC).isoformat()
    )

    # Build patch document
    patch_doc = {
        "schema_version": "1.0",
        "pipeline_version": CHATX_VERSION,
        "generated_at": generated_at,
        "timestamp_mode": timestamp_mode,
        "inputs": {
            "task_queue_path": str(task_queue_path),
            "run_ids": sorted([rs["run_id"] for rs in run_summaries]),
            "input_hash": input_hash,
        },
        "patches": _patches_to_dicts(patches),
    }

    # Write outputs
    patch_path = output_dir / "TASK_QUEUE_PATCH.json"
    write_json_strict(
        data=patch_doc,
        output_path=patch_path,
        schema_name="task_queue_patch",
    )

    _write_priority_delta(patches, task_queue, output_dir, run_summaries)
    _write_conflict_ledger_updates(
        patches, run_summaries, output_dir, conflict_ledger_path
    )


def _load_run_summaries(run_paths: list[Path], max_runs: int) -> list[dict[str, Any]]:
    """Load and validate run summaries."""
    summaries = []

    for run_path in run_paths[:max_runs]:
        summary_path = run_path / "RUN_SUMMARY.json"
        if not summary_path.exists():
            continue

        with open(summary_path) as f:
            summary = json.load(f)

        ok, errors = validate_data(summary, "run_summary", strict=True)
        if not ok:
            raise ValueError(f"Invalid run summary {summary_path}: {errors}")

        summaries.append(summary)

    # Sort by run_id for determinism
    summaries.sort(key=lambda s: s["run_id"])

    return summaries


def _generate_patches(
    run_summaries: list[dict[str, Any]], task_queue: dict[str, Any]
) -> list[Patch]:
    """Generate patches from run summaries using deterministic rules."""
    patches_by_task: dict[str, list[Patch]] = {}

    # Build task lookup
    task_lookup = {pkt["id"]: pkt for pkt in task_queue["packets"]}

    for summary in run_summaries:
        task_id = summary["task_packet"]["id"]

        if task_id not in task_lookup:
            continue

        run_id = summary["run_id"]
        claims = summary["claims"]["items"]
        status = summary["status"]

        # Apply deterministic rules
        task_patches = []

        # Rule 1: Any test_failed → set risk=high, priority=1
        failed_claims = [c for c in claims if c["claim_type"] == "test_failed"]
        if failed_claims:
            evidence = [Evidence(run_id, c["claim_id"]) for c in failed_claims]
            task_patches.append(
                Patch(
                    task_id=task_id,
                    op="set_risk",
                    value="high",
                    reason="Test failures detected",
                    evidence=evidence,
                )
            )
            task_patches.append(
                Patch(
                    task_id=task_id,
                    op="set_priority",
                    value=1,
                    reason="Needs immediate fix due to test failures",
                    evidence=evidence,
                )
            )

        # Rule 2: test_passed + checklist_completed → status=done, priority=5
        passed_claims = [c for c in claims if c["claim_type"] == "test_passed"]
        if passed_claims and status["checklist_completed"]:
            evidence = [Evidence(run_id, c["claim_id"]) for c in passed_claims]
            task_patches.append(
                Patch(
                    task_id=task_id,
                    op="set_status",
                    value="done",
                    reason="Tests passed and checklist completed",
                    evidence=evidence,
                )
            )
            task_patches.append(
                Patch(
                    task_id=task_id,
                    op="set_priority",
                    value=5,
                    reason="Task completed successfully",
                    evidence=evidence,
                )
            )

        # Rule 3: Only constraint_respected → append note
        constraint_claims = [
            c for c in claims if c["claim_type"] == "constraint_respected"
        ]
        test_claims = [
            c
            for c in claims
            if c["claim_type"] in ["test_passed", "test_failed"]
        ]
        if constraint_claims and not test_claims:
            evidence = [Evidence(run_id, c["claim_id"]) for c in constraint_claims]
            task_patches.append(
                Patch(
                    task_id=task_id,
                    op="append_note",
                    value="Constraints confirmed, tests not recorded",
                    reason="Only constraint claims found",
                    evidence=evidence,
                )
            )

        # Rule 4: verification_outputs_present=false → append note
        if not status["verification_outputs_present"]:
            # Use any available claim as evidence, or empty if no claims
            evidence = [Evidence(run_id, claims[0]["claim_id"])] if claims else []
            task_patches.append(
                Patch(
                    task_id=task_id,
                    op="append_note",
                    value="Verification outputs missing; treat completion as unverified",
                    reason="No verification outputs in evidence",
                    evidence=evidence,
                )
            )

        # Collect patches for this task
        if task_id not in patches_by_task:
            patches_by_task[task_id] = []
        patches_by_task[task_id].extend(task_patches)

    # Merge patches from multiple runs
    merged_patches = _merge_patches(patches_by_task)

    # Sort for determinism: by (task_id, op)
    merged_patches.sort(key=lambda p: (p.task_id, p.op))

    return merged_patches


def _merge_patches(patches_by_task: dict[str, list[Patch]]) -> list[Patch]:
    """Merge patches for the same task from multiple runs."""
    merged: list[Patch] = []

    for task_id, patches in sorted(patches_by_task.items()):
        # Group by operation
        by_op: dict[str, list[Patch]] = {}
        for patch in patches:
            if patch.op not in by_op:
                by_op[patch.op] = []
            by_op[patch.op].append(patch)

        for op, op_patches in by_op.items():
            if op == "set_risk":
                # Take max severity
                risk_order = {"low": 0, "med": 1, "high": 2}
                max_patch = max(op_patches, key=lambda p: risk_order.get(p.value, 0))
                # Combine evidence from all runs
                all_evidence = []
                for p in op_patches:
                    all_evidence.extend(p.evidence)
                merged.append(
                    Patch(
                        task_id=task_id,
                        op=op,
                        value=max_patch.value,
                        reason=max_patch.reason,
                        evidence=all_evidence,
                    )
                )

            elif op == "set_priority":
                # Take min numeric if any failures, else if done priority=5
                has_failure = any(
                    p.value == 1 for p in op_patches
                )
                if has_failure:
                    min_patch = min(op_patches, key=lambda p: p.value)
                    all_evidence = []
                    for p in op_patches:
                        all_evidence.extend(p.evidence)
                    merged.append(
                        Patch(
                            task_id=task_id,
                            op=op,
                            value=min_patch.value,
                            reason=min_patch.reason,
                            evidence=all_evidence,
                        )
                    )
                else:
                    # All done (priority=5)
                    all_evidence = []
                    for p in op_patches:
                        all_evidence.extend(p.evidence)
                    merged.append(
                        Patch(
                            task_id=task_id,
                            op=op,
                            value=5,
                            reason="Task completed successfully",
                            evidence=all_evidence,
                        )
                    )

            elif op == "set_status":
                # Take latest status (deterministic by run_id sort)
                latest_patch = op_patches[-1]
                all_evidence = []
                for p in op_patches:
                    all_evidence.extend(p.evidence)
                merged.append(
                    Patch(
                        task_id=task_id,
                        op=op,
                        value=latest_patch.value,
                        reason=latest_patch.reason,
                        evidence=all_evidence,
                    )
                )

            elif op == "append_note":
                # Append notes in stable order by run_id
                # Sort patches by run_id from evidence
                sorted_patches = sorted(
                    op_patches,
                    key=lambda p: p.evidence[0].run_id if p.evidence else "",
                )
                for patch in sorted_patches:
                    merged.append(patch)

    return merged


def _patches_to_dicts(patches: list[Patch]) -> list[dict[str, Any]]:
    """Convert patches to dictionaries for JSON serialization."""
    return [
        {
            "task_id": p.task_id,
            "op": p.op,
            "value": p.value,
            "reason": p.reason,
            "evidence": [{"run_id": e.run_id, "claim_id": e.claim_id} for e in p.evidence],
        }
        for p in patches
    ]


def _compute_input_hash(task_queue_path: Path, run_summaries: list[dict[str, Any]]) -> str:
    """Compute deterministic hash of inputs."""
    # Hash task queue file
    with open(task_queue_path, "rb") as f:
        tq_hash = hashlib.sha256(f.read()).hexdigest()

    # Hash concatenated run summary hashes
    summary_hashes = [rs["hashes"]["summary_hash"] for rs in run_summaries]
    combined = tq_hash + "".join(sorted(summary_hashes))

    return hashlib.sha256(combined.encode()).hexdigest()


def _write_priority_delta(
    patches: list[Patch],
    task_queue: dict[str, Any],
    output_dir: Path,
    run_summaries: list[dict[str, Any]],
) -> None:
    """Write PRIORITY_DELTA.md report."""
    task_lookup = {pkt["id"]: pkt for pkt in task_queue["packets"]}

    # Group patches by task
    patches_by_task: dict[str, list[Patch]] = {}
    for patch in patches:
        if patch.task_id not in patches_by_task:
            patches_by_task[patch.task_id] = []
        patches_by_task[patch.task_id].append(patch)

    lines = ["# Priority Delta Report\n"]
    lines.append(f"**Tasks affected:** {len(patches_by_task)}\n")
    lines.append(f"**Runs ingested:** {len(run_summaries)}\n")
    lines.append("\n---\n")

    for task_id in sorted(patches_by_task.keys()):
        task = task_lookup.get(task_id)
        if not task:
            continue

        task_patches = patches_by_task[task_id]

        lines.append(f"\n## {task_id} — {task['title']}\n")

        # Before
        lines.append("\n**Before:**\n")
        lines.append(f"- Priority: {task.get('priority', 'N/A')}\n")
        lines.append(f"- Risk: {task.get('risk', 'N/A')}\n")
        if task.get("notes"):
            lines.append(f"- Notes: {task['notes'][:100]}...\n")

        # After (proposed)
        lines.append("\n**Proposed changes:**\n")
        for patch in task_patches:
            lines.append(f"- {patch.op} = `{patch.value}` ({patch.reason})\n")

        # Evidence
        lines.append("\n**Evidence:**\n")
        for patch in task_patches:
            for ev in patch.evidence:
                lines.append(f"- {ev.run_id}: {ev.claim_id}\n")

        lines.append("\n---\n")

    output_path = output_dir / "PRIORITY_DELTA.md"
    output_path.write_text("".join(lines))


def _write_conflict_ledger_updates(
    patches: list[Patch],
    run_summaries: list[dict[str, Any]],
    output_dir: Path,
    conflict_ledger_path: Path | None,
) -> None:
    """Write CONFLICT_LEDGER_UPDATES.md."""
    lines = ["# Conflict Ledger Updates\n"]
    lines.append("\n**Summary:**\n")
    lines.append(f"- Runs analyzed: {len(run_summaries)}\n")
    lines.append(f"- Patches generated: {len(patches)}\n")
    lines.append("\n---\n")

    # Check if we have resolution evidence
    has_resolution_evidence = any(
        any(
            c["claim_type"] in ["test_passed", "constraint_respected"]
            for c in rs["claims"]["items"]
        )
        for rs in run_summaries
    )

    if conflict_ledger_path and conflict_ledger_path.exists():
        lines.append("\n## Conflict Ledger Analysis\n")
        lines.append(f"Source: {conflict_ledger_path}\n\n")

        if has_resolution_evidence:
            lines.append(
                "**Resolution hints:** Evidence contains test_passed or "
                "constraint_respected claims. Review runs for potential conflict resolutions.\n"
            )
        else:
            lines.append(
                "**Insufficient evidence:** No test_passed or constraint_respected "
                "claims found to propose conflict resolutions.\n"
            )
    else:
        lines.append("\n## Conflict Ledger Analysis\n")
        lines.append("No conflict ledger provided or found.\n")

    lines.append("\n---\n")
    lines.append("\n*Note: This file provides suggestions only. "
                "It does not modify the conflict ledger.*\n")

    output_path = output_dir / "CONFLICT_LEDGER_UPDATES.md"
    output_path.write_text("".join(lines))
