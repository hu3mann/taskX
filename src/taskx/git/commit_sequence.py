"""Commit-by-commit sequencing from task packet COMMIT PLAN."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from taskx.git.worktree import (
    VALID_DIRTY_POLICIES,
    append_dirty_state_entry,
    git_changed_files,
    git_staged_files,
    run_git_command,
    stash_changes,
)
from taskx.obs.run_artifacts import (
    ALLOWLIST_DIFF_FILENAME,
    COMMIT_SEQUENCE_RUN_FILENAME,
    DIRTY_STATE_FILENAME,
    PROMOTION_LEGACY_FILENAME,
    PROMOTION_TOKEN_FILENAME,
    RUN_ENVELOPE_FILENAME,
    WORKTREE_FILENAME,
)
from taskx.pipeline.task_runner.parser import parse_task_packet
from taskx.pipeline.task_runner.types import CommitStep, TaskPacketInfo


def _timestamp(mode: str) -> str:
    if mode == "deterministic":
        return "1970-01-01T00:00:00Z"
    return datetime.now(UTC).isoformat()


def _allowlist_violation_count(payload: dict[str, Any]) -> int:
    violations = payload.get("violations")
    if isinstance(violations, list):
        return len(violations)
    if isinstance(violations, dict):
        count = violations.get("count")
        if isinstance(count, int):
            return count
        items = violations.get("items")
        if isinstance(items, list):
            return len(items)
    return 0


def _load_worktree_metadata(run_dir: Path) -> tuple[dict[str, Any], Path]:
    worktree_path = run_dir / WORKTREE_FILENAME
    if not worktree_path.exists():
        raise RuntimeError(f"Required artifact missing: {worktree_path}")

    payload = json.loads(worktree_path.read_text(encoding="utf-8"))
    required = ["repo_root", "worktree_path", "branch", "base_branch", "remote"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise RuntimeError(f"{WORKTREE_FILENAME} missing required keys: {missing}")

    resolved_worktree = Path(payload["worktree_path"]).resolve()
    if not resolved_worktree.exists():
        raise RuntimeError(f"Worktree path does not exist: {resolved_worktree}")

    return payload, resolved_worktree


def _resolve_task_packet_path(run_dir: Path) -> Path:
    envelope_path = run_dir / RUN_ENVELOPE_FILENAME
    if envelope_path.exists():
        payload = json.loads(envelope_path.read_text(encoding="utf-8"))
        task_packet = payload.get("task_packet", {})
        candidate = task_packet.get("path") if isinstance(task_packet, dict) else None
        if isinstance(candidate, str) and candidate.strip():
            packet_path = Path(candidate).expanduser().resolve()
            if packet_path.exists():
                return packet_path

    local_copy = run_dir / "TASK_PACKET.md"
    if local_copy.exists():
        return local_copy.resolve()

    raise RuntimeError(
        "Unable to locate task packet source. "
        "Checked RUN_ENVELOPE task_packet.path and run-local TASK_PACKET.md."
    )


def _execute_verification(
    *,
    commands: list[str],
    cwd: Path,
) -> tuple[bool, list[dict[str, Any]], str | None]:
    results: list[dict[str, Any]] = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        result = {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        results.append(result)
        if completed.returncode != 0:
            return False, results, command
    return True, results, None


def _stash_outside_changes(
    *,
    run_dir: Path,
    worktree_path: Path,
    dirty_policy: str,
    all_step_allowlist: set[str],
    report: dict[str, Any],
) -> None:
    changed = sorted(set(git_changed_files(worktree_path)))
    outside = [path for path in changed if path not in all_step_allowlist]
    if not outside:
        return

    report["dirty_handling"]["outside_allowlist_files"] = outside
    if dirty_policy == "refuse":
        raise RuntimeError(
            "Found changes outside COMMIT PLAN allowlists. "
            "Use --dirty-policy stash to stash them and continue."
        )

    stash_message = f"taskx:commit-sequence:{run_dir.name}"
    stash_output = stash_changes(
        cwd=worktree_path,
        message=stash_message,
        include_untracked=True,
        paths=outside,
    )
    report["dirty_handling"]["stashed_outside_allowlist"] = True
    report["dirty_handling"]["stash_message"] = stash_message
    report["dirty_handling"]["stash_output"] = stash_output
    append_dirty_state_entry(
        run_dir,
        {
            "event": "commit_sequence",
            "policy": dirty_policy,
            "action": "stash",
            "scope": "worktree_outside_commit_plan_allowlists",
            "created_at": _timestamp("wallclock"),
            "changed_files": outside,
            "stash_message": stash_message,
            "stash_output": stash_output,
        },
    )


def _commit_message(packet: TaskPacketInfo, step: CommitStep) -> str:
    packet_id = packet.id if packet.id.startswith("TP_") else f"TP_{packet.id}"
    return f"{packet_id} {step.step_id}: {step.message}"


def commit_sequence(
    run_dir: Path,
    *,
    allow_unpromoted: bool = False,
    timestamp_mode: str = "deterministic",
    dirty_policy: str = "refuse",
) -> dict[str, Any]:
    """Create one commit per COMMIT PLAN step inside the run worktree."""
    resolved_run_dir = run_dir.resolve()
    report_path = resolved_run_dir / COMMIT_SEQUENCE_RUN_FILENAME
    errors: list[str] = []
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": _timestamp(timestamp_mode),
        "timestamp_mode": timestamp_mode,
        "run_dir": str(resolved_run_dir),
        "status": "failed",
        "errors": errors,
        "policies": {
            "allow_unpromoted": allow_unpromoted,
            "dirty_policy": dirty_policy,
        },
        "artifacts": {
            "allowlist_diff": str((resolved_run_dir / ALLOWLIST_DIFF_FILENAME).resolve()),
            "worktree": str((resolved_run_dir / WORKTREE_FILENAME).resolve()),
            "dirty_state": str((resolved_run_dir / DIRTY_STATE_FILENAME).resolve()),
            "commit_sequence_report": str(report_path.resolve()),
        },
        "promotion": {
            "required": not allow_unpromoted,
            "found": False,
            "token_path": None,
        },
        "git": {
            "branch": None,
            "head_before": None,
            "head_after": None,
            "worktree_path": None,
        },
        "task_packet": {
            "id": None,
            "path": None,
            "commit_plan_steps": 0,
            "verification_commands_default": [],
        },
        "dirty_handling": {
            "outside_allowlist_files": [],
            "stashed_outside_allowlist": False,
            "stash_message": None,
            "stash_output": None,
        },
        "steps": [],
    }

    try:
        if dirty_policy not in VALID_DIRTY_POLICIES:
            raise RuntimeError(
                f"Unsupported dirty policy: {dirty_policy}. "
                f"Expected one of {sorted(VALID_DIRTY_POLICIES)}."
            )
        if not resolved_run_dir.exists():
            raise RuntimeError(f"Run directory does not exist: {resolved_run_dir}")

        allowlist_path = resolved_run_dir / ALLOWLIST_DIFF_FILENAME
        if not allowlist_path.exists():
            raise RuntimeError(f"Required artifact missing: {allowlist_path}")
        allowlist_payload = json.loads(allowlist_path.read_text(encoding="utf-8"))
        violation_count = _allowlist_violation_count(allowlist_payload)
        if violation_count > 0:
            raise RuntimeError(
                f"Allowlist report contains {violation_count} violation(s); refusing to commit."
            )

        promotion_paths = [
            resolved_run_dir / PROMOTION_TOKEN_FILENAME,
            resolved_run_dir / PROMOTION_LEGACY_FILENAME,
        ]
        promotion_found_path = next((path for path in promotion_paths if path.exists()), None)
        if promotion_found_path is not None:
            report["promotion"]["found"] = True
            report["promotion"]["token_path"] = str(promotion_found_path.resolve())
        if promotion_found_path is None and not allow_unpromoted:
            raise RuntimeError(
                "Run is not promoted. Expected PROMOTION_TOKEN.json or PROMOTION.json."
            )

        worktree_payload, worktree_path = _load_worktree_metadata(resolved_run_dir)
        report["git"]["worktree_path"] = str(worktree_path)
        report["worktree"] = worktree_payload

        current_branch = run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=worktree_path,
        )
        report["git"]["branch"] = current_branch
        if current_branch == "main":
            raise RuntimeError("Refusing commit-sequence on main branch.")

        staged_files_before = git_staged_files(worktree_path)
        if staged_files_before:
            raise RuntimeError(
                "Refusing commit-sequence with pre-staged index entries present."
            )

        packet_path = _resolve_task_packet_path(resolved_run_dir)
        packet = parse_task_packet(packet_path)
        report["task_packet"]["id"] = packet.id
        report["task_packet"]["path"] = str(packet_path)
        report["task_packet"]["verification_commands_default"] = list(
            packet.verification_commands
        )

        if not packet.commit_plan:
            raise RuntimeError("Task packet has no COMMIT PLAN; commit-sequence requires it.")

        report["task_packet"]["commit_plan_steps"] = len(packet.commit_plan)

        all_step_allowlist: set[str] = set()
        for step in packet.commit_plan:
            all_step_allowlist.update(step.allowlist)

        _stash_outside_changes(
            run_dir=resolved_run_dir,
            worktree_path=worktree_path,
            dirty_policy=dirty_policy,
            all_step_allowlist=all_step_allowlist,
            report=report,
        )

        report["git"]["head_before"] = run_git_command(["rev-parse", "HEAD"], cwd=worktree_path)

        for step in packet.commit_plan:
            _stash_outside_changes(
                run_dir=resolved_run_dir,
                worktree_path=worktree_path,
                dirty_policy=dirty_policy,
                all_step_allowlist=all_step_allowlist,
                report=report,
            )

            changed_files = sorted(set(git_changed_files(worktree_path)))
            staged_for_step = sorted(set(changed_files).intersection(step.allowlist))
            step_report: dict[str, Any] = {
                "step_id": step.step_id,
                "message": step.message,
                "allowlist": list(step.allowlist),
                "changed_files": changed_files,
                "staged_files": staged_for_step,
                "verification_commands": (
                    list(step.verify) if step.verify is not None else list(packet.verification_commands)
                ),
                "verification_results": [],
                "commit_message": None,
                "commit_hash": None,
                "status": "failed",
            }

            if not staged_for_step:
                report["steps"].append(step_report)
                raise RuntimeError(
                    f"Step {step.step_id} has no changed files in its allowlist; refusing empty commit."
                )

            for path in staged_for_step:
                run_git_command(["add", "--", path], cwd=worktree_path)

            verification_commands = (
                step.verify if step.verify is not None else packet.verification_commands
            )
            ok, verification_results, failed_command = _execute_verification(
                commands=verification_commands,
                cwd=worktree_path,
            )
            step_report["verification_results"] = verification_results
            if not ok:
                run_git_command(["reset", "--mixed", "HEAD"], cwd=worktree_path)
                report["steps"].append(step_report)
                raise RuntimeError(
                    f"Verification failed for step {step.step_id} on command: {failed_command}"
                )

            commit_message = _commit_message(packet, step)
            run_git_command(["commit", "-m", commit_message], cwd=worktree_path)
            step_report["commit_message"] = commit_message
            step_report["commit_hash"] = run_git_command(["rev-parse", "HEAD"], cwd=worktree_path)
            step_report["status"] = "passed"
            report["steps"].append(step_report)

        report["git"]["head_after"] = run_git_command(["rev-parse", "HEAD"], cwd=worktree_path)
        report["status"] = "passed"
        return report
    except Exception as exc:  # pragma: no cover - explicit failure path serialization
        errors.append(str(exc))
        return report
    finally:
        try:
            resolved_run_dir.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                f"{json.dumps(report, indent=2, sort_keys=True)}\n",
                encoding="utf-8",
            )
        except OSError as write_error:
            if str(write_error) not in errors:
                errors.append(f"Failed to write {COMMIT_SEQUENCE_RUN_FILENAME}: {write_error}")
