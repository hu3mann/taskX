"""Run promotion gate implementation."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from taskx.pipeline.promotion.types import Evidence, PromotionToken
from taskx.schemas.validator import validate_data
from taskx.utils.json_output import write_json_strict

CHATX_VERSION = "0.1.0"


def promote_run(
    run_dir: Path,
    timestamp_mode: str = "deterministic",
    require_run_summary: bool = False,
    out_dir: Path | None = None,
) -> PromotionToken:
    """
    Promote a run by validating all completion requirements.

    Args:
        run_dir: Path to run folder
        timestamp_mode: "deterministic" or "wallclock"
        require_run_summary: If true, RUN_SUMMARY.json must be present
        out_dir: Output directory (defaults to run_dir)

    Returns:
        PromotionToken with status passed or failed

    Raises:
        FileNotFoundError: If required files missing
        RuntimeError: If validation fails
    """
    if out_dir is None:
        out_dir = run_dir

    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load and validate required inputs
    allowlist_diff_path = run_dir / "ALLOWLIST_DIFF.json"
    run_envelope_path = run_dir / "RUN_ENVELOPE.json"
    run_summary_path = run_dir / "RUN_SUMMARY.json"
    evidence_md_path = run_dir / "EVIDENCE.md"

    if not allowlist_diff_path.exists():
        raise FileNotFoundError(f"ALLOWLIST_DIFF.json not found in {run_dir}")

    if not run_envelope_path.exists():
        raise FileNotFoundError(f"RUN_ENVELOPE.json not found in {run_dir}")

    # Load allowlist diff
    with open(allowlist_diff_path) as f:
        allowlist_diff = json.load(f)

    # Validate allowlist diff schema
    ok, errors = validate_data(allowlist_diff, "allowlist_diff", strict=True)
    if not ok:
        raise RuntimeError(f"ALLOWLIST_DIFF.json schema validation failed: {errors}")

    # Load run envelope
    with open(run_envelope_path) as f:
        run_envelope = json.load(f)

    # Validate run envelope schema
    ok, errors = validate_data(run_envelope, "run_envelope", strict=True)
    if not ok:
        raise RuntimeError(f"RUN_ENVELOPE.json schema validation failed: {errors}")

    run_id = run_envelope["run_id"]

    # Load run summary if present
    run_summary = None
    run_summary_path_str = None
    if run_summary_path.exists():
        with open(run_summary_path) as f:
            run_summary = json.load(f)

        # Validate run summary schema
        ok, errors = validate_data(run_summary, "run_summary", strict=True)
        if not ok:
            raise RuntimeError(f"RUN_SUMMARY.json schema validation failed: {errors}")

        run_summary_path_str = str(run_summary_path)
    elif require_run_summary:
        raise FileNotFoundError(f"RUN_SUMMARY.json required but not found in {run_dir}")

    # 2. Collect evidence
    evidence = [
        Evidence(kind="allowlist_diff", path=str(allowlist_diff_path)),
        Evidence(kind="run_envelope", path=str(run_envelope_path)),
    ]

    if run_summary:
        evidence.append(Evidence(kind="run_summary", path=str(run_summary_path)))

    if evidence_md_path.exists():
        evidence.append(Evidence(kind="evidence_md", path=str(evidence_md_path)))

    # 3. Apply promotion decision rules
    reasons = []
    passed = True

    # Rule 1: Allowlist violations must be zero
    violation_count = allowlist_diff["violations"]["count"]
    if violation_count > 0:
        passed = False
        reasons.append(f"Allowlist gate has {violation_count} violation(s)")

    # Rule 2: No disallowed files
    disallowed = allowlist_diff["changed_files"]["disallowed"]
    if disallowed:
        passed = False
        reasons.append(f"Found {len(disallowed)} disallowed file change(s)")

    # Rule 3: Verification evidence must be present
    # First check if allowlist diff already flagged missing evidence
    has_evidence_violation = False
    for violation in allowlist_diff["violations"]["items"]:
        if violation["type"] == "missing_verification_evidence":
            has_evidence_violation = True
            passed = False
            reasons.append("Verification evidence missing (flagged by allowlist gate)")
            break

    # Also do direct check
    if not has_evidence_violation and not _has_verification_evidence(evidence_md_path):
        passed = False
        reasons.append("Verification evidence missing in EVIDENCE.md")

    # Rule 4: Check for test failures in run summary
    if run_summary:
        claims = run_summary.get("claims", {}).get("items", [])
        failed_claims = [c for c in claims if c.get("claim_type") == "test_failed"]
        if failed_claims:
            passed = False
            reasons.append(f"Found {len(failed_claims)} test_failed claim(s) in run summary")

    # If passed, add positive reason
    if passed:
        reasons.append("All promotion checks passed")

    # 4. Build token
    status = "passed" if passed else "failed"

    token = PromotionToken(
        run_id=run_id,
        status=status,
        reasons=reasons,
        evidence=evidence,
        token_hash="",  # Will be computed
        run_dir=str(run_dir),
        allowlist_diff_path=str(allowlist_diff_path),
        run_envelope_path=str(run_envelope_path),
        run_summary_path=run_summary_path_str,
    )

    # 5. Compute token hash
    token.token_hash = _compute_token_hash(token, timestamp_mode)

    # 6. Write outputs
    _write_promotion_json(token, out_dir, timestamp_mode)
    _write_promotion_md(token, out_dir, run_envelope)

    return token


def _has_verification_evidence(evidence_path: Path) -> bool:
    """Check if EVIDENCE.md contains verification outputs."""
    if not evidence_path.exists():
        return False

    content = evidence_path.read_text()

    # Look for command outputs section
    if "## Command outputs pasted" not in content:
        return False

    # Check for non-empty content after the heading
    lines = content.split("\n")
    in_section = False
    has_content = False

    for line in lines:
        if "## Command outputs pasted" in line:
            in_section = True
            continue

        if in_section:
            # If we hit another heading, stop
            if line.startswith("##"):
                break
            # Check for non-empty, non-whitespace line
            if line.strip():
                has_content = True
                break

    return has_content


def _compute_token_hash(token: PromotionToken, timestamp_mode: str) -> str:
    """Compute deterministic hash of token excluding the hash itself."""
    # Build canonical data (excluding token_hash)
    timestamp = (
        "1970-01-01T00:00:00Z" if timestamp_mode == "deterministic"
        else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    canonical = {
        "schema_version": "1.0",
        "pipeline_version": CHATX_VERSION,
        "run_id": token.run_id,
        "generated_at": timestamp,
        "timestamp_mode": timestamp_mode,
        "status": token.status,
        "inputs": {
            "run_dir": token.run_dir,
            "allowlist_diff_path": token.allowlist_diff_path,
            "run_envelope_path": token.run_envelope_path,
            "run_summary_path": token.run_summary_path,
        },
        "decision": {
            "reasons": token.reasons,
            "evidence": [{"kind": e.kind, "path": e.path} for e in token.evidence],
        },
    }

    # Compute hash
    canonical_str = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_str.encode()).hexdigest()


def _write_promotion_json(
    token: PromotionToken,
    out_dir: Path,
    timestamp_mode: str
) -> None:
    """Write PROMOTION.json."""
    timestamp = (
        "1970-01-01T00:00:00Z" if timestamp_mode == "deterministic"
        else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    data = {
        "schema_version": "1.0",
        "pipeline_version": CHATX_VERSION,
        "run_id": token.run_id,
        "generated_at": timestamp,
        "timestamp_mode": timestamp_mode,
        "status": token.status,
        "inputs": {
            "run_dir": token.run_dir,
            "allowlist_diff_path": token.allowlist_diff_path,
            "run_envelope_path": token.run_envelope_path,
            "run_summary_path": token.run_summary_path,
        },
        "decision": {
            "reasons": token.reasons,
            "evidence": [{"kind": e.kind, "path": e.path} for e in token.evidence],
        },
        "hashes": {
            "token_hash": token.token_hash,
        }
    }

    output_path = out_dir / "PROMOTION.json"
    write_json_strict(
        data=data,
        output_path=output_path,
        schema_name="promotion_token"
    )


def _write_promotion_md(
    token: PromotionToken,
    out_dir: Path,
    run_envelope: dict
) -> None:
    """Write PROMOTION.md."""
    status_icon = "✅ PASSED" if token.status == "passed" else "❌ FAILED"

    task_packet = run_envelope.get("task_packet", {})
    task_id = task_packet.get("id", "unknown")
    task_title = task_packet.get("title", "unknown")

    lines = [
        "# Run Promotion Report",
        "",
        f"**Status:** {status_icon}",
        f"**Run ID:** {token.run_id}",
        f"**Task:** {task_id} — {task_title}",
        "",
        "## Decision Reasons",
        ""
    ]

    for reason in token.reasons:
        lines.append(f"- {reason}")

    lines.extend([
        "",
        "## Evidence Files",
        ""
    ])

    for ev in token.evidence:
        lines.append(f"- `{ev.kind}`: {ev.path}")

    lines.extend([
        "",
        "---",
        f"*Token hash: {token.token_hash}*"
    ])

    output_path = out_dir / "PROMOTION.md"
    output_path.write_text("\n".join(lines))
