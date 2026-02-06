"""Loop orchestrator - runs lifecycle stages A5→A6→A7→A8→A9."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from rich.console import Console

from taskx import __version__


from taskx.pipeline.evidence.collector import collect_evidence
from taskx.pipeline.loop.types import LoopInputs, StageResult
from taskx.pipeline.spec_feedback.feedback import generate_feedback

try:
    from taskx.spec_mining.miner import mine_spec
except ImportError:
    mine_spec = None  # type: ignore[assignment]
from taskx.pipeline.task_compiler.compiler import compile_task_queue
from taskx.pipeline.task_runner.parser import parse_task_packet
from taskx.pipeline.task_runner.runner import create_run_workspace
from taskx.utils.json_output import write_json_strict

TASKX_VERSION = "0.1.0"
STAGE_ORDER = ["mine_spec", "compile_tasks", "run_task", "collect_evidence", "spec_feedback"]


def run_loop(
    loop_id: str,
    loop_dir: Path,
    inputs: LoopInputs,
    timestamp_mode: str = "deterministic",
    runs_path: Path | None = None,
) -> None:
    """Run the full lifecycle loop.

    Args:
        loop_id: Unique loop identifier
        loop_dir: Root directory for this loop's outputs
        inputs: Loop configuration inputs
        timestamp_mode: "deterministic" or "wallclock"
        runs_path: Optional external runs directory for feedback
    """
    loop_dir.mkdir(parents=True, exist_ok=True)

    # Track stages
    stages: dict[str, StageResult] = {}
    stop_execution = False

    # Stage 1: Mine spec (A5)
    stages["mine_spec"] = _run_mine_spec(
        loop_dir, inputs, timestamp_mode, stop_execution
    )
    if stages["mine_spec"].status == "failed":
        stop_execution = True

    # Stage 2: Compile tasks (A6)
    stages["compile_tasks"] = _run_compile_tasks(
        loop_dir, inputs, timestamp_mode, stop_execution, stages["mine_spec"]
    )
    if stages["compile_tasks"].status == "failed":
        stop_execution = True

    # Stage 3: Run task (A7) - optional
    stages["run_task"] = _run_task_workspace(
        loop_dir, inputs, timestamp_mode, stop_execution, stages["compile_tasks"]
    )
    if stages["run_task"].status == "failed":
        # Don't stop - optional stages can fail without blocking feedback
        pass

    # Stage 4: Collect evidence (A8) - optional
    stages["collect_evidence"] = _run_collect_evidence(
        loop_dir, inputs, timestamp_mode, stop_execution, stages["run_task"]
    )

    # Stage 5: Spec feedback (A9) - optional
    stages["spec_feedback"] = _run_spec_feedback(
        loop_dir, inputs, timestamp_mode, stop_execution, stages["compile_tasks"], runs_path
    )

    # Compute aggregate hash
    loop_hash = _compute_loop_hash(stages)

    # Build envelope
    envelope = _build_envelope(
        loop_id=loop_id,
        inputs=inputs,
        stages=stages,
        loop_hash=loop_hash,
        timestamp_mode=timestamp_mode,
    )

    # Write outputs
    envelope_path = loop_dir / "LOOP_ENVELOPE.json"
    write_json_strict(
        data=envelope,
        output_path=envelope_path,
        schema_name="loop_envelope",
    )

    _write_stage_log(loop_dir, loop_id, inputs, stages)


def _run_mine_spec(
    loop_dir: Path,
    inputs: LoopInputs,
    timestamp_mode: str,
    stop: bool,
) -> StageResult:
    """Run A5 spec mining stage."""

    if stop:
        return _skipped_stage()

    started_at = _get_timestamp(timestamp_mode)
    out_dir = loop_dir / "spec_mine"
    outputs = []

    try:
        # Call A5 miner with default includes/excludes
        mine_spec(
            repo_root=inputs.root,
            output_dir=out_dir,
            include_globs=["docs/**/*.md", "**/*.md"],
            exclude_globs=["node_modules/**", "venv/**", ".venv/**"],
            max_file_kb=500,
            pipeline_version=TASKX_VERSION,
            format="both",
        )

        # Collect outputs
        if out_dir.exists():
            for f in sorted(out_dir.rglob("*")):
                if f.is_file():
                    outputs.append(str(f.relative_to(loop_dir)))

        ended_at = _get_timestamp(timestamp_mode)
        stage_hash = _compute_stage_hash(loop_dir, outputs)

        return StageResult(
            enabled=True,
            status="ok",
            started_at=started_at,
            ended_at=ended_at,
            out_dir=str(out_dir.relative_to(loop_dir)),
            inputs={"repo_root": str(inputs.root)},
            outputs=outputs,
            hashes={"stage_output_hash": stage_hash},
            error=None,
        )

    except Exception as e:
        ended_at = _get_timestamp(timestamp_mode)
        return StageResult(
            enabled=True,
            status="failed",
            started_at=started_at,
            ended_at=ended_at,
            out_dir=str(out_dir.relative_to(loop_dir)) if out_dir else None,
            inputs={"repo_root": str(inputs.root)},
            outputs=outputs,
            hashes={},
            error=str(e),
        )


def _run_compile_tasks(
    loop_dir: Path,
    inputs: LoopInputs,
    timestamp_mode: str,
    stop: bool,
    mine_result: StageResult,
) -> StageResult:
    """Run A6 task compilation stage."""
    if stop:
        return _skipped_stage()

    started_at = _get_timestamp(timestamp_mode)
    out_dir = loop_dir / "task_queue"
    outputs = []

    try:
        # Find spec and source index from A5
        spec_mine_dir = loop_dir / "spec_mine"
        spec_path = spec_mine_dir / "MASTER_DESIGN_SPEC_V3.md"
        source_index_path = spec_mine_dir / "SOURCE_INDEX.json"

        if not spec_path.exists():
            raise FileNotFoundError(f"Spec not found: {spec_path}")
        if not source_index_path.exists():
            raise FileNotFoundError(f"Source index not found: {source_index_path}")

        # Call A6 compiler
        compile_task_queue(
            spec_path=spec_path,
            source_index_path=source_index_path,
            output_dir=out_dir,
            mode=inputs.mode,
            max_packets=inputs.max_packets,
            seed=inputs.seed,
            pipeline_version=TASKX_VERSION,
            timestamp_mode=timestamp_mode,
        )

        # Collect outputs
        if out_dir.exists():
            for f in sorted(out_dir.rglob("*")):
                if f.is_file():
                    outputs.append(str(f.relative_to(loop_dir)))

        ended_at = _get_timestamp(timestamp_mode)
        stage_hash = _compute_stage_hash(loop_dir, outputs)

        return StageResult(
            enabled=True,
            status="ok",
            started_at=started_at,
            ended_at=ended_at,
            out_dir=str(out_dir.relative_to(loop_dir)),
            inputs={
                "spec_path": str(spec_path),
                "source_index_path": str(source_index_path),
                "mode": inputs.mode,
                "max_packets": inputs.max_packets,
                "seed": inputs.seed,
            },
            outputs=outputs,
            hashes={"stage_output_hash": stage_hash},
            error=None,
        )

    except Exception as e:
        ended_at = _get_timestamp(timestamp_mode)
        return StageResult(
            enabled=True,
            status="failed",
            started_at=started_at,
            ended_at=ended_at,
            out_dir=str(out_dir.relative_to(loop_dir)) if out_dir else None,
            inputs={
                "mode": inputs.mode,
                "max_packets": inputs.max_packets,
                "seed": inputs.seed,
            },
            outputs=outputs,
            hashes={},
            error=str(e),
        )


def _run_task_workspace(
    loop_dir: Path,
    inputs: LoopInputs,
    timestamp_mode: str,
    stop: bool,
    compile_result: StageResult,
) -> StageResult:
    """Run A7 task workspace generation stage (optional)."""
    if not inputs.run_task or stop:
        return _skipped_stage()

    started_at = _get_timestamp(timestamp_mode)
    run_id = inputs.run_id if inputs.run_id else f"RUN_{inputs.run_task}"
    runs_dir = loop_dir / "runs"
    run_dir = runs_dir / run_id
    outputs = []

    try:
        # Find task packet
        task_queue_dir = loop_dir / "task_queue" / "TASK_PACKETS"
        if not task_queue_dir.exists():
            raise FileNotFoundError(f"Task packets directory not found: {task_queue_dir}")

        # Find packet file matching task id
        packet_file = None
        for f in task_queue_dir.glob(f"{inputs.run_task}_*.md"):
            packet_file = f
            break

        if not packet_file:
            raise FileNotFoundError(f"Task packet not found for {inputs.run_task}")

        # Parse task packet
        task_info = parse_task_packet(packet_file)

        # Call A7 runner
        create_run_workspace(
            task_packet_path=packet_file,
            run_id=run_id,
            output_dir=runs_dir,
            timestamp_mode=timestamp_mode,
            pipeline_version=__version__,
        )

        # Collect outputs
        if run_dir.exists():
            for f in sorted(run_dir.rglob("*")):
                if f.is_file():
                    outputs.append(str(f.relative_to(loop_dir)))

        ended_at = _get_timestamp(timestamp_mode)
        stage_hash = _compute_stage_hash(loop_dir, outputs)

        return StageResult(
            enabled=True,
            status="ok",
            started_at=started_at,
            ended_at=ended_at,
            out_dir=str(run_dir.relative_to(loop_dir)),
            inputs={
                "task_id": inputs.run_task,
                "run_id": run_id,
                "packet_file": str(packet_file),
            },
            outputs=outputs,
            hashes={"stage_output_hash": stage_hash},
            error=None,
        )

    except Exception as e:
        ended_at = _get_timestamp(timestamp_mode)
        return StageResult(
            enabled=True,
            status="failed",
            started_at=started_at,
            ended_at=ended_at,
            out_dir=str(run_dir.relative_to(loop_dir)) if run_dir else None,
            inputs={"task_id": inputs.run_task, "run_id": run_id},
            outputs=outputs,
            hashes={},
            error=str(e),
        )


def _run_collect_evidence(
    loop_dir: Path,
    inputs: LoopInputs,
    timestamp_mode: str,
    stop: bool,
    run_result: StageResult,
) -> StageResult:
    """Run A8 evidence collection stage (optional)."""
    if not inputs.collect_evidence or stop:
        return _skipped_stage()

    # Need successful A7 run
    if run_result.status != "ok":
        return _skipped_stage()

    started_at = _get_timestamp(timestamp_mode)
    run_dir = loop_dir / run_result.out_dir if run_result.out_dir else None
    outputs = []

    if not run_dir or not run_dir.exists():
        return StageResult(
            enabled=True,
            status="failed",
            started_at=started_at,
            ended_at=_get_timestamp(timestamp_mode),
            out_dir=None,
            inputs={},
            outputs=[],
            hashes={},
            error="Run directory not found",
        )

    try:
        # Call A8 collector
        artifacts = collect_evidence(
            run_dir=run_dir,
            timestamp_mode=timestamp_mode,
            max_claims=200,
            max_evidence_chars=200000,
            pipeline_version=TASKX_VERSION,
        )

        # Collect outputs (from artifacts dict)
        for key in ["summary", "ledger", "bundle"]:
            if key in artifacts:
                artifact_path = Path(artifacts[key])
                if artifact_path.exists():
                    outputs.append(str(artifact_path.relative_to(loop_dir)))

        ended_at = _get_timestamp(timestamp_mode)
        stage_hash = _compute_stage_hash(loop_dir, outputs)

        return StageResult(
            enabled=True,
            status="ok",
            started_at=started_at,
            ended_at=ended_at,
            out_dir=str(run_dir.relative_to(loop_dir)),
            inputs={"run_dir": str(run_dir)},
            outputs=outputs,
            hashes={"stage_output_hash": stage_hash},
            error=None,
        )

    except Exception as e:
        ended_at = _get_timestamp(timestamp_mode)
        return StageResult(
            enabled=True,
            status="failed",
            started_at=started_at,
            ended_at=ended_at,
            out_dir=str(run_dir.relative_to(loop_dir)) if run_dir else None,
            inputs={"run_dir": str(run_dir) if run_dir else None},
            outputs=outputs,
            hashes={},
            error=str(e),
        )


def _run_spec_feedback(
    loop_dir: Path,
    inputs: LoopInputs,
    timestamp_mode: str,
    stop: bool,
    compile_result: StageResult,
    runs_path: Path | None,
) -> StageResult:
    """Run A9 spec feedback stage (optional)."""
    if not inputs.feedback or stop:
        return _skipped_stage()

    started_at = _get_timestamp(timestamp_mode)
    out_dir = loop_dir / "spec_feedback"
    outputs = []

    try:
        # Determine runs directory
        target_runs = runs_path or loop_dir / "runs"

        if not target_runs.exists():
            raise FileNotFoundError(f"Runs directory not found: {target_runs}")

        # Find run folders
        run_paths = []
        for subdir in sorted(target_runs.iterdir()):
            if subdir.is_dir() and (subdir / "RUN_SUMMARY.json").exists():
                run_paths.append(subdir)

        if not run_paths:
            raise ValueError("No run folders with RUN_SUMMARY.json found")

        # Find task queue
        task_queue_path = loop_dir / "task_queue" / "TASK_QUEUE.json"
        if not task_queue_path.exists():
            raise FileNotFoundError(f"Task queue not found: {task_queue_path}")

        # Optional conflict ledger
        _cl_path = loop_dir / "spec_mine" / "DESIGN_CONFLICT_LEDGER_V2.md"
        conflict_ledger_path: Path | None = _cl_path if _cl_path.exists() else None

        # Call A9 feedback
        generate_feedback(
            run_paths=run_paths,
            task_queue_path=task_queue_path,
            output_dir=out_dir,
            conflict_ledger_path=conflict_ledger_path,
            timestamp_mode=timestamp_mode,
            max_runs=200,
        )

        # Collect outputs
        if out_dir.exists():
            for f in sorted(out_dir.rglob("*")):
                if f.is_file():
                    outputs.append(str(f.relative_to(loop_dir)))

        ended_at = _get_timestamp(timestamp_mode)
        stage_hash = _compute_stage_hash(loop_dir, outputs)

        return StageResult(
            enabled=True,
            status="ok",
            started_at=started_at,
            ended_at=ended_at,
            out_dir=str(out_dir.relative_to(loop_dir)),
            inputs={
                "runs_path": str(target_runs),
                "task_queue_path": str(task_queue_path),
                "run_count": len(run_paths),
            },
            outputs=outputs,
            hashes={"stage_output_hash": stage_hash},
            error=None,
        )

    except Exception as e:
        ended_at = _get_timestamp(timestamp_mode)
        return StageResult(
            enabled=True,
            status="failed",
            started_at=started_at,
            ended_at=ended_at,
            out_dir=str(out_dir.relative_to(loop_dir)) if out_dir else None,
            inputs={"runs_path": str(runs_path) if runs_path else None},
            outputs=outputs,
            hashes={},
            error=str(e),
        )


def _skipped_stage() -> StageResult:
    """Create a skipped stage result."""
    return StageResult(
        enabled=False,
        status="skipped",
        started_at=None,
        ended_at=None,
        out_dir=None,
        inputs={},
        outputs=[],
        hashes={},
        error=None,
    )


def _get_timestamp(mode: str) -> str:
    """Get timestamp based on mode."""
    if mode == "deterministic":
        return "1970-01-01T00:00:00Z"
    else:
        return datetime.now(UTC).isoformat()


def _compute_stage_hash(loop_dir: Path, outputs: list[str]) -> str:
    """Compute stage output hash."""
    if not outputs:
        return "0" * 64  # Empty hash for no outputs

    # Build canonical string
    hash_parts = []
    for relpath in sorted(outputs):
        file_path = loop_dir / relpath
        if file_path.exists():
            with open(file_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            hash_parts.append(f"{relpath}:{file_hash}")

    combined = "\n".join(hash_parts)
    return hashlib.sha256(combined.encode()).hexdigest()


def _compute_loop_hash(stages: dict[str, StageResult]) -> str:
    """Compute aggregate loop hash from all stage hashes in fixed order."""
    stage_hashes = []

    for stage_name in STAGE_ORDER:
        if stage_name in stages:
            stage_hash = stages[stage_name].hashes.get("stage_output_hash", "0" * 64)
            stage_hashes.append(stage_hash)

    combined = "".join(stage_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()


def _build_envelope(
    loop_id: str,
    inputs: LoopInputs,
    stages: dict[str, StageResult],
    loop_hash: str,
    timestamp_mode: str,
) -> dict[str, Any]:
    """Build loop envelope document."""
    generated_at = _get_timestamp(timestamp_mode)

    # Convert stages to dicts
    stages_dict = {}
    for name, result in stages.items():
        stages_dict[name] = {
            "enabled": result.enabled,
            "status": result.status,
            "started_at": result.started_at,
            "ended_at": result.ended_at,
            "out_dir": result.out_dir,
            "inputs": result.inputs,
            "outputs": result.outputs,
            "hashes": result.hashes,
            "error": result.error,
        }

    return {
        "schema_version": "1.0",
        "pipeline_version": TASKX_VERSION,
        "loop_id": loop_id,
        "generated_at": generated_at,
        "timestamp_mode": timestamp_mode,
        "inputs": {
            "root": str(inputs.root),
            "mode": inputs.mode,
            "max_packets": inputs.max_packets,
            "seed": inputs.seed,
            "run_task": inputs.run_task,
            "run_id": inputs.run_id,
            "collect_evidence": inputs.collect_evidence,
            "feedback": inputs.feedback,
        },
        "stages": stages_dict,
        "aggregate": {
            "loop_hash": loop_hash,
        },
    }


def _write_stage_log(
    loop_dir: Path,
    loop_id: str,
    inputs: LoopInputs,
    stages: dict[str, StageResult],
) -> None:
    """Write human-readable stage log."""
    lines = ["# Loop Stage Log\n"]
    lines.append(f"\n**Loop ID:** {loop_id}\n")
    lines.append("\n## Inputs\n")
    lines.append(f"- Root: {inputs.root}\n")
    lines.append(f"- Mode: {inputs.mode}\n")
    lines.append(f"- Max packets: {inputs.max_packets}\n")
    lines.append(f"- Seed: {inputs.seed}\n")
    lines.append(f"- Run task: {inputs.run_task or 'None'}\n")
    lines.append(f"- Run ID: {inputs.run_id or 'Auto-generated'}\n")
    lines.append(f"- Collect evidence: {inputs.collect_evidence}\n")
    lines.append(f"- Feedback: {inputs.feedback}\n")

    lines.append("\n## Stages\n")

    for stage_name in STAGE_ORDER:
        if stage_name in stages:
            result = stages[stage_name]
            status_icon = {
                "ok": "✓",
                "failed": "✗",
                "skipped": "—",
            }.get(result.status, "?")

            lines.append(f"\n### {stage_name}\n")
            lines.append(f"**Status:** {status_icon} {result.status}\n")

            if result.out_dir:
                lines.append(f"**Output:** {result.out_dir}\n")

            if result.outputs:
                lines.append(f"**Files:** {len(result.outputs)}\n")

            if result.error:
                lines.append(f"**Error:** {result.error}\n")

    log_path = loop_dir / "STAGE_LOG.md"
    log_path.write_text("".join(lines))
