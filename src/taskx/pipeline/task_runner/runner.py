"""Task packet runner."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from taskx.pipeline.task_runner.parser import parse_task_packet
from taskx.utils.json_output import write_json_strict

if TYPE_CHECKING:
    from pathlib import Path

    from taskx.pipeline.task_runner.types import TaskPacketInfo


def create_run_workspace(
    *,
    task_packet_path: Path,
    output_dir: Path,
    run_id: str | None = None,
    timestamp_mode: str = "deterministic",
    pipeline_version: str,
    dry_run: bool = False,
) -> dict[str, str]:
    """Create a structured run workspace for task packet execution.

    Args:
        task_packet_path: Path to task packet markdown file
        output_dir: Base output directory for runs
        run_id: Optional run ID (generated if not provided)
        timestamp_mode: "deterministic" or "wallclock"
        pipeline_version: Pipeline version string
        dry_run: If True, don't write files, just return planned paths

    Returns:
        Dict with paths to created artifacts

    Raises:
        ValueError: If task packet is invalid
    """
    # Parse task packet
    packet_info = parse_task_packet(task_packet_path)

    # Generate run_id if not provided
    if run_id is None:
        run_id = str(uuid.uuid4())

    # Determine timestamp
    if timestamp_mode == "deterministic":
        generated_at = "1970-01-01T00:00:00Z"
    elif timestamp_mode == "wallclock":
        generated_at = datetime.now(UTC).isoformat()
    else:
        raise ValueError(f"Invalid timestamp_mode: {timestamp_mode}")

    # Create run directory
    run_dir = output_dir / run_id

    if dry_run:
        # Just return planned paths
        return {
            "run_dir": str(run_dir),
            "envelope": str(run_dir / "RUN_ENVELOPE.json"),
            "task_packet": str(run_dir / "TASK_PACKET.md"),
            "plan": str(run_dir / "PLAN.md"),
            "checklist": str(run_dir / "CHECKLIST.md"),
            "runlog": str(run_dir / "RUNLOG.md"),
            "evidence": str(run_dir / "EVIDENCE.md"),
            "commands": str(run_dir / "COMMANDS.sh"),
        }

    # Create directory
    run_dir.mkdir(parents=True, exist_ok=True)

    # Copy task packet
    task_packet_dest = run_dir / "TASK_PACKET.md"
    task_packet_dest.write_bytes(task_packet_path.read_bytes())

    # Generate workspace files
    _generate_plan(run_dir / "PLAN.md", packet_info, generated_at)
    _generate_checklist(run_dir / "CHECKLIST.md", packet_info)
    _generate_runlog(run_dir / "RUNLOG.md", packet_info, generated_at)
    _generate_evidence(run_dir / "EVIDENCE.md", packet_info)
    _generate_commands_script(run_dir / "COMMANDS.sh", packet_info)

    # Build workspace file list (sorted)
    workspace_files = [
        {"path": "CHECKLIST.md", "purpose": "Execution checklist"},
        {"path": "COMMANDS.sh", "purpose": "Verification commands script"},
        {"path": "EVIDENCE.md", "purpose": "Evidence collection template"},
        {"path": "PLAN.md", "purpose": "Implementation plan"},
        {"path": "RUN_ENVELOPE.json", "purpose": "Run metadata envelope"},
        {"path": "RUNLOG.md", "purpose": "Execution log"},
        {"path": "TASK_PACKET.md", "purpose": "Original task packet"},
    ]

    # Build envelope
    envelope_dict = {
        "schema_version": "1.0",
        "pipeline_version": pipeline_version,
        "run_id": run_id,
        "generated_at": generated_at,
        "timestamp_mode": timestamp_mode,
        "task_packet": {
            "path": str(task_packet_path),
            "sha256": packet_info.sha256,
            "id": packet_info.id,
            "title": packet_info.title,
            "allowlist": packet_info.allowlist,
            "sources": packet_info.sources,
        },
        "workspace": {
            "root": str(run_dir),
            "files": workspace_files,
        },
        "commands": {
            "verification": packet_info.verification_commands,
        },
        "notes": f"Run workspace for {packet_info.id}",
    }

    # Write envelope
    envelope_path = run_dir / "RUN_ENVELOPE.json"
    write_json_strict(
        data=envelope_dict,
        output_path=envelope_path,
        schema_name="run_envelope",
    )

    return {
        "run_dir": str(run_dir),
        "envelope": str(envelope_path),
        "task_packet": str(task_packet_dest),
        "plan": str(run_dir / "PLAN.md"),
        "checklist": str(run_dir / "CHECKLIST.md"),
        "runlog": str(run_dir / "RUNLOG.md"),
        "evidence": str(run_dir / "EVIDENCE.md"),
        "commands": str(run_dir / "COMMANDS.sh"),
    }


def _generate_plan(path: Path, packet: TaskPacketInfo, timestamp: str) -> None:
    """Generate PLAN.md template."""
    content = f"""# Implementation Plan — {packet.id}

**Task:** {packet.title}

**Run started:** {timestamp}

---

## Prime Directive

**Task packets are law.**

All changes must:
- Stay within the allowlist
- Satisfy all goals
- Pass all verification commands
- Preserve existing functionality

---

## Planned Edits (Allowlist)

The following files/paths are allowed for modification:

"""

    for item in packet.allowlist:
        content += f"- `{item}`\n"

    content += """
---

## Implementation Plan

1. **Read relevant files**
   - Review current implementation
   - Understand dependencies
   - Identify modification points

2. **Apply changes within allowlist**
   - Make minimal, surgical edits
   - Follow project conventions
   - Document decisions

3. **Run verification commands**
   - Execute all commands from COMMANDS.sh
   - Capture output to EVIDENCE.md

4. **Record evidence**
   - Command outputs
   - Diff summaries
   - File changes list

---

## Notes

(Add implementation notes here as work progresses)
"""

    path.write_text(content, encoding="utf-8")


def _generate_checklist(path: Path, packet: TaskPacketInfo) -> None:
    """Generate CHECKLIST.md template."""
    content = f"""# Execution Checklist — {packet.id}

## Pre-Implementation

- [ ] Task packet parsed and understood
- [ ] Allowlist validated
- [ ] Dependencies identified

## Implementation

- [ ] Edits limited to allowlist only
- [ ] No schema changes unless packet allowlists it
- [ ] Tests added/updated as required
- [ ] Code follows project conventions

## Verification

- [ ] All verification commands executed
- [ ] Command outputs captured in EVIDENCE.md
- [ ] Tests pass
- [ ] No unexpected side effects

## Evidence

- [ ] Evidence captured (logs, diffs)
- [ ] File changes list recorded
- [ ] RUN_ENVELOPE.json schema-valid

## Completion

- [ ] All checklist items complete
- [ ] Ready for review
"""

    path.write_text(content, encoding="utf-8")


def _generate_runlog(path: Path, packet: TaskPacketInfo, timestamp: str) -> None:
    """Generate RUNLOG.md template."""
    content = f"""# Run Log — {packet.id}

**Task:** {packet.title}

**Start time:** {timestamp}

**Operator / Agent:** _[Fill in]_

---

## Summary

_[Brief summary of what was accomplished]_

---

## Steps Taken

_[Detailed steps taken during implementation]_

1.
2.
3.

---

## Commands Executed

_[Record of commands run and their results]_

```bash
# Example:
# $ command
# output...
```

---

## Notes / Anomalies

_[Any unexpected behavior, decisions, or deviations from plan]_

---

## Completion

**End time:** _[Fill in]_

**Status:** _[success/partial/failed]_
"""

    path.write_text(content, encoding="utf-8")


def _generate_evidence(path: Path, packet: TaskPacketInfo) -> None:
    """Generate EVIDENCE.md template."""
    content = f"""# Evidence — {packet.id}

**Task:** {packet.title}

---

## Command Outputs

### Verification Commands

_[Paste command outputs here]_

```
$ command1
output...

$ command2
output...
```

---

## Diff Summary

_[Summary of code changes made]_

```diff
# Example diff format:
# --- a/file.py
# +++ b/file.py
# @@ -10,3 +10,4 @@
#  existing line
# +new line
```

---

## Files Changed

_[List of files modified, created, or deleted]_

**Modified:**
-

**Created:**
-

**Deleted:**
-

---

## Test Results

_[Test output and results]_

```
# Example:
# pytest output...
# 10 passed
```
"""

    path.write_text(content, encoding="utf-8")


def _generate_commands_script(path: Path, packet: TaskPacketInfo) -> None:
    """Generate COMMANDS.sh script."""
    content = "#!/bin/bash\n"
    content += "set -euo pipefail\n\n"
    content += f"# Verification commands for {packet.id}\n"
    content += f"# Task: {packet.title}\n\n"

    for cmd in packet.verification_commands:
        content += f"{cmd}\n"

    path.write_text(content, encoding="utf-8")
    # Make executable
    path.chmod(0o755)
