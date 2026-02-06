"""Evidence collector for task packet runs."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from taskx.pipeline.evidence.types import Claim, RunStatus
from taskx.utils.json_output import write_json_strict


def collect_evidence(
    *,
    run_dir: Path,
    timestamp_mode: str = "deterministic",
    max_claims: int = 200,
    max_evidence_chars: int = 200000,
    pipeline_version: str,
) -> dict[str, str]:
    """Collect evidence from a completed run workspace.

    Args:
        run_dir: Path to run directory
        timestamp_mode: "deterministic" or "wallclock"
        max_claims: Maximum number of claims to extract
        max_evidence_chars: Maximum characters in evidence bundle
        pipeline_version: Pipeline version string

    Returns:
        Dict with paths to generated artifacts

    Raises:
        ValueError: If run directory or RUN_ENVELOPE.json invalid
    """
    # Validate run directory exists
    if not run_dir.exists():
        raise ValueError(f"Run directory not found: {run_dir}")

    # Load RUN_ENVELOPE.json (hard-fail if missing)
    envelope_path = run_dir / "RUN_ENVELOPE.json"
    if not envelope_path.exists():
        raise ValueError(f"RUN_ENVELOPE.json not found in {run_dir}")

    with envelope_path.open() as f:
        envelope = json.load(f)

    # Extract task packet info
    task_packet = envelope["task_packet"]
    task_id = task_packet["id"]
    run_id = envelope["run_id"]

    # Check which files are present
    files_present = _check_files_present(run_dir)

    # Load file contents (gracefully handle missing)
    file_contents = _load_file_contents(run_dir, files_present)

    # Extract claims
    claims = _extract_claims(
        file_contents=file_contents,
        task_id=task_id,
        max_claims=max_claims,
    )

    # Analyze status
    status = _analyze_status(file_contents)

    # Compute hashes
    run_folder_hash = _compute_run_folder_hash(run_dir, files_present)

    # Determine timestamp
    if timestamp_mode == "deterministic":
        generated_at = "1970-01-01T00:00:00Z"
    elif timestamp_mode == "wallclock":
        generated_at = datetime.now(UTC).isoformat()
    else:
        raise ValueError(f"Invalid timestamp_mode: {timestamp_mode}")

    # Build summary dict (excluding summary_hash initially)
    summary_dict = {
        "schema_version": "1.0",
        "pipeline_version": pipeline_version,
        "run_id": run_id,
        "generated_at": generated_at,
        "timestamp_mode": timestamp_mode,
        "task_packet": {
            "id": task_packet["id"],
            "title": task_packet["title"],
            "path": task_packet["path"],
            "sha256": task_packet["sha256"],
        },
        "status": {
            "checklist_completed": status.checklist_completed,
            "verification_commands_listed": status.verification_commands_listed,
            "verification_outputs_present": status.verification_outputs_present,
            "anomalies": status.anomalies,
        },
        "files_present": files_present,
        "claims": {
            "count": len(claims),
            "items": [
                {
                    "claim_id": c.claim_id,
                    "claim_type": c.claim_type,
                    "text": c.text,
                    "evidence_source": c.evidence_source,
                    "confidence": c.confidence,
                }
                for c in claims
            ],
        },
        "hashes": {
            "run_folder_hash": run_folder_hash,
            "summary_hash": "",  # Placeholder
        },
    }

    # Compute summary hash
    summary_hash = _compute_summary_hash(summary_dict)
    summary_dict["hashes"]["summary_hash"] = summary_hash

    # Write RUN_SUMMARY.json
    summary_path = run_dir / "RUN_SUMMARY.json"
    write_json_strict(
        data=summary_dict,
        output_path=summary_path,
        schema_name="run_summary",
    )

    # Write CLAIMS_LEDGER.csv
    ledger_path = run_dir / "CLAIMS_LEDGER.csv"
    _write_claims_ledger(ledger_path, claims, run_id, task_id)

    # Write EVIDENCE_BUNDLE.md
    bundle_path = run_dir / "EVIDENCE_BUNDLE.md"
    _write_evidence_bundle(
        bundle_path,
        envelope,
        file_contents,
        claims,
        max_evidence_chars,
    )

    return {
        "summary": str(summary_path),
        "ledger": str(ledger_path),
        "bundle": str(bundle_path),
    }


def _check_files_present(run_dir: Path) -> dict[str, bool]:
    """Check which known files are present in run directory."""
    known_files = [
        "RUNLOG.md",
        "EVIDENCE.md",
        "CHECKLIST.md",
        "PLAN.md",
        "COMMANDS.sh",
        "RUN_ENVELOPE.json",
        "TASK_PACKET.md",
    ]

    return {
        Path(f).stem if f.endswith(".json") or f.endswith(".sh") else Path(f).stem:
        (run_dir / f).exists()
        for f in known_files
    }


def _load_file_contents(run_dir: Path, files_present: dict[str, bool]) -> dict[str, str]:
    """Load contents of present files."""
    contents = {}

    file_map = {
        "RUNLOG": "RUNLOG.md",
        "EVIDENCE": "EVIDENCE.md",
        "CHECKLIST": "CHECKLIST.md",
        "PLAN": "PLAN.md",
        "COMMANDS": "COMMANDS.sh",
    }

    for key, filename in file_map.items():
        if files_present.get(key, False):
            path = run_dir / filename
            try:
                contents[key] = path.read_text(encoding="utf-8")
            except Exception:
                contents[key] = ""
        else:
            contents[key] = ""

    return contents


def _extract_claims(
    *,
    file_contents: dict[str, str],
    task_id: str,
    max_claims: int,
) -> list[Claim]:
    """Extract claims from file contents using conservative rules.

    Rules:
    1. - [x] in CHECKLIST → constraint_respected (0.8)
    2. PASSED: in EVIDENCE → test_passed (0.9)
    3. FAILED: in EVIDENCE → test_failed (0.9)
    4. DONE: in RUNLOG → change_made (0.7)
    """
    claims = []
    claim_counter = 1

    # Rule 1: Checklist completed items
    if file_contents.get("CHECKLIST"):
        for line in file_contents["CHECKLIST"].split("\n"):
            if claim_counter > max_claims:
                break

            line = line.strip()
            if line.startswith("- [x]") or line.startswith("* [x]"):
                text = line[5:].strip()[:280]  # Max 280 chars
                if text:
                    claims.append(Claim(
                        claim_id=f"{task_id}_C{claim_counter:03d}",
                        claim_type="constraint_respected",
                        text=text,
                        evidence_source="CHECKLIST",
                        confidence=0.8,
                    ))
                    claim_counter += 1

    # Rule 2 & 3: PASSED/FAILED in EVIDENCE
    if file_contents.get("EVIDENCE"):
        for line in file_contents["EVIDENCE"].split("\n"):
            if claim_counter > max_claims:
                break

            line = line.strip()
            if line.startswith("PASSED:"):
                text = line[7:].strip()[:280]
                if text:
                    claims.append(Claim(
                        claim_id=f"{task_id}_C{claim_counter:03d}",
                        claim_type="test_passed",
                        text=text,
                        evidence_source="EVIDENCE",
                        confidence=0.9,
                    ))
                    claim_counter += 1
            elif line.startswith("FAILED:"):
                text = line[7:].strip()[:280]
                if text:
                    claims.append(Claim(
                        claim_id=f"{task_id}_C{claim_counter:03d}",
                        claim_type="test_failed",
                        text=text,
                        evidence_source="EVIDENCE",
                        confidence=0.9,
                    ))
                    claim_counter += 1

    # Rule 4: DONE in RUNLOG
    if file_contents.get("RUNLOG"):
        for line in file_contents["RUNLOG"].split("\n"):
            if claim_counter > max_claims:
                break

            line = line.strip()
            if line.startswith("DONE:"):
                text = line[5:].strip()[:280]
                if text:
                    claims.append(Claim(
                        claim_id=f"{task_id}_C{claim_counter:03d}",
                        claim_type="change_made",
                        text=text,
                        evidence_source="RUNLOG",
                        confidence=0.7,
                    ))
                    claim_counter += 1

    return claims[:max_claims]


def _analyze_status(file_contents: dict[str, str]) -> RunStatus:
    """Analyze run status from file contents."""
    # Check if checklist has any completed items
    checklist_completed = False
    if file_contents.get("CHECKLIST"):
        checklist_completed = "- [x]" in file_contents["CHECKLIST"] or "* [x]" in file_contents["CHECKLIST"]

    # Check if commands are listed
    verification_commands_listed = False
    if file_contents.get("COMMANDS"):
        # Has content beyond shebang/set -e
        lines = [l.strip() for l in file_contents["COMMANDS"].split("\n") if l.strip()]
        verification_commands_listed = len(lines) > 2  # More than just shebang + set -e

    # Check if verification outputs are present
    verification_outputs_present = False
    if file_contents.get("EVIDENCE"):
        # Look for command output section markers
        evidence_lower = file_contents["EVIDENCE"].lower()
        verification_outputs_present = (
            "command output" in evidence_lower or
            "$ " in file_contents["EVIDENCE"] or  # Shell prompt
            "PASSED:" in file_contents["EVIDENCE"] or
            "FAILED:" in file_contents["EVIDENCE"]
        )

    # Detect anomalies
    anomalies: list[str] = []

    return RunStatus(
        checklist_completed=checklist_completed,
        verification_commands_listed=verification_commands_listed,
        verification_outputs_present=verification_outputs_present,
        anomalies=anomalies,
    )


def _compute_run_folder_hash(run_dir: Path, files_present: dict[str, bool]) -> str:
    """Compute hash of run folder contents."""
    file_map = {
        "RUNLOG": "RUNLOG.md",
        "EVIDENCE": "EVIDENCE.md",
        "CHECKLIST": "CHECKLIST.md",
        "PLAN": "PLAN.md",
        "COMMANDS": "COMMANDS.sh",
        "RUN_ENVELOPE": "RUN_ENVELOPE.json",
        "TASK_PACKET": "TASK_PACKET.md",
    }

    file_hashes = []

    for key in sorted(files_present.keys()):
        if files_present[key]:
            filename = file_map.get(key, f"{key}.md")
            filepath = run_dir / filename

            if filepath.exists():
                file_bytes = filepath.read_bytes()
                file_hash = hashlib.sha256(file_bytes).hexdigest()
                file_hashes.append(f"{filename}:{file_hash}")

    # Concatenate and hash
    combined = "\n".join(file_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()


def _compute_summary_hash(summary_dict: dict) -> str:
    """Compute hash of summary excluding summary_hash field."""
    # Make a copy and remove summary_hash
    summary_copy = json.loads(json.dumps(summary_dict))  # Deep copy
    summary_copy["hashes"]["summary_hash"] = ""

    # Canonical JSON
    canonical = json.dumps(summary_copy, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _write_claims_ledger(path: Path, claims: list[Claim], run_id: str, task_id: str) -> None:
    """Write claims to CSV ledger."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Write header
        writer.writerow(["run_id", "task_id", "claim_id", "claim_type", "text", "evidence_source", "confidence"])

        # Write claims
        for claim in claims:
            writer.writerow([
                run_id,
                task_id,
                claim.claim_id,
                claim.claim_type,
                claim.text,
                claim.evidence_source,
                claim.confidence,
            ])


def _write_evidence_bundle(
    path: Path,
    envelope: dict,
    file_contents: dict[str, str],
    claims: list[Claim],
    max_chars: int,
) -> None:
    """Write evidence bundle markdown."""
    sections = []

    # Header
    sections.append("# Evidence Bundle\n")

    # Run Envelope
    sections.append("## Run Envelope\n")
    sections.append("```json\n")
    sections.append(json.dumps(envelope, indent=2))
    sections.append("\n```\n")

    # Checklist
    if file_contents.get("CHECKLIST"):
        sections.append("## Checklist\n")
        sections.append(file_contents["CHECKLIST"])
        sections.append("\n")

    # Plan
    if file_contents.get("PLAN"):
        sections.append("## Plan\n")
        sections.append(file_contents["PLAN"])
        sections.append("\n")

    # Runlog
    if file_contents.get("RUNLOG"):
        sections.append("## Runlog\n")
        sections.append(file_contents["RUNLOG"])
        sections.append("\n")

    # Evidence (may be truncated)
    if file_contents.get("EVIDENCE"):
        sections.append("## Evidence\n")
        evidence_section = file_contents["EVIDENCE"]

        # Check if we need to truncate
        current_length = sum(len(s) for s in sections)
        available_chars = max_chars - current_length - 500  # Reserve for claims section

        if len(evidence_section) > available_chars:
            truncated = evidence_section[:available_chars]
            sections.append(truncated)
            sections.append("\n\n[... Evidence section truncated due to length ...]\n")
        else:
            sections.append(evidence_section)
            sections.append("\n")

    # Commands
    if file_contents.get("COMMANDS"):
        sections.append("## Commands\n")
        sections.append("```bash\n")
        sections.append(file_contents["COMMANDS"])
        sections.append("\n```\n")

    # Claims Extracted
    sections.append("## Claims Extracted\n")
    for claim in claims:
        sections.append(f"- **{claim.claim_id}** ({claim.claim_type}, confidence={claim.confidence}): {claim.text}\n")

    # Write bundle
    bundle_content = "\n".join(sections)
    path.write_text(bundle_content, encoding="utf-8")
