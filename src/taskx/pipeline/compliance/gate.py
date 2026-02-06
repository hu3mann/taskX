"""Allowlist compliance gate implementation."""

import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

from taskx.pipeline.compliance.types import AllowlistDiff, Violation
from taskx.utils.json_output import write_json_strict

CHATX_VERSION = "0.1.0"


def run_allowlist_gate(
    run_dir: Path,
    repo_root: Path,
    timestamp_mode: str = "deterministic",
    require_verification_evidence: bool = True,
    diff_mode: str = "auto",
    out_dir: Path | None = None,
) -> AllowlistDiff:
    """
    Run allowlist compliance gate on a completed run.

    Args:
        run_dir: Path to run folder (contains RUN_ENVELOPE.json)
        repo_root: Repository root path
        timestamp_mode: "deterministic" or "wallclock"
        require_verification_evidence: Require verification evidence in EVIDENCE.md
        diff_mode: "git", "fs", or "auto"
        out_dir: Output directory (defaults to run_dir)

    Returns:
        AllowlistDiff result object

    Raises:
        FileNotFoundError: If required files missing
        RuntimeError: If validation fails
    """
    if out_dir is None:
        out_dir = run_dir

    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load and validate RUN_ENVELOPE
    envelope_path = run_dir / "RUN_ENVELOPE.json"
    if not envelope_path.exists():
        raise FileNotFoundError(f"RUN_ENVELOPE.json not found in {run_dir}")

    with open(envelope_path) as f:
        envelope = json.load(f)

    run_id = envelope["run_id"]
    task_packet = envelope["task_packet"]
    task_id = task_packet["id"]
    task_title = task_packet["title"]
    allowlist = task_packet["allowlist"]

    if not allowlist:
        raise RuntimeError("Task packet allowlist is empty")

    # 2. Determine diff mode
    actual_diff_mode = _determine_diff_mode(diff_mode, repo_root)

    # 3. Detect changed files
    changed_files = _detect_changed_files(actual_diff_mode, repo_root, envelope)

    # 4. Classify files as allowed vs disallowed
    allowed, disallowed = _classify_files(changed_files, allowlist, repo_root)

    # 5. Detect violations
    violations = []

    # Check for allowlist violations
    if disallowed:
        violations.append(Violation(
            type="allowlist_violation",
            message=f"Found {len(disallowed)} file(s) changed outside allowlist",
            files=sorted(disallowed)
        ))

    # Check for verification evidence
    if require_verification_evidence:
        evidence_path = run_dir / "EVIDENCE.md"
        if not _has_verification_evidence(evidence_path):
            violations.append(Violation(
                type="missing_verification_evidence",
                message="EVIDENCE.md missing or lacks command outputs section",
                files=[]
            ))

    # Warn about fs mode limitations
    if actual_diff_mode == "fs" and require_verification_evidence:
        violations.append(Violation(
            type="tooling_limitation",
            message="Using filesystem mode (mtime-based); git mode recommended for accuracy",
            files=[]
        ))

    # 6. Compute diff hash
    diff_hash = _compute_diff_hash(allowed, disallowed)

    # 7. Build result
    result = AllowlistDiff(
        run_id=run_id,
        task_id=task_id,
        task_title=task_title,
        allowlist=allowlist,
        diff_mode_used=actual_diff_mode,
        allowed_files=sorted(allowed),
        disallowed_files=sorted(disallowed),
        violations=violations,
        diff_hash=diff_hash
    )

    # 8. Write outputs
    _write_allowlist_diff_json(result, out_dir, repo_root, timestamp_mode)
    _write_violations_md(result, out_dir, actual_diff_mode)

    return result


def _determine_diff_mode(diff_mode: str, repo_root: Path) -> str:
    """Determine actual diff mode to use."""
    if diff_mode == "git":
        return "git"
    elif diff_mode == "fs":
        return "fs"
    else:  # auto
        # Check if .git exists and git is available
        git_dir = repo_root / ".git"
        if git_dir.exists() and shutil.which("git"):
            return "git"
        return "fs"


def _detect_changed_files(diff_mode: str, repo_root: Path, envelope: dict) -> set[str]:
    """Detect changed files using specified mode."""
    if diff_mode == "git":
        return _detect_changed_files_git(repo_root)
    else:
        return _detect_changed_files_fs(repo_root, envelope)


def _detect_changed_files_git(repo_root: Path) -> set[str]:
    """Detect changed files using git status."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )

        changed = set()
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            # Format: "XY filename" where XY are status codes
            # Extract filename (handle renames, etc.)
            parts = line.strip().split(maxsplit=1)
            if len(parts) >= 2:
                filename = parts[1]
                # Handle renames "old -> new"
                if " -> " in filename:
                    filename = filename.split(" -> ")[1]
                # Normalize to POSIX path
                changed.add(Path(filename).as_posix())

        return changed
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: {e}")


def _detect_changed_files_fs(repo_root: Path, envelope: dict) -> set[str]:
    """
    Detect changed files using filesystem mtime.

    This is a weak heuristic but deterministic.
    Files with mtime newer than envelope generated_at are considered changed.
    """
    # Parse envelope timestamp
    generated_at_str = envelope.get("generated_at", "1970-01-01T00:00:00Z")
    try:
        if generated_at_str == "1970-01-01T00:00:00Z":
            # Deterministic mode - can't reliably use mtime
            # Return empty set and rely on violations to catch this
            return set()
        else:
            envelope_time = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
            envelope_timestamp = envelope_time.timestamp()
    except (ValueError, AttributeError):
        # Can't parse timestamp, return empty
        return set()

    changed = set()

    # Walk repo tree
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue

        # Skip hidden files and directories
        if any(part.startswith(".") for part in path.relative_to(repo_root).parts):
            continue

        # Check mtime
        if path.stat().st_mtime > envelope_timestamp:
            rel_path = path.relative_to(repo_root).as_posix()
            changed.add(rel_path)

    return changed


def _classify_files(
    changed_files: set[str],
    allowlist: list[str],
    repo_root: Path
) -> tuple[list[str], list[str]]:
    """
    Classify changed files as allowed or disallowed.

    Returns:
        (allowed_files, disallowed_files)
    """
    allowed = []
    disallowed = []

    for filepath in changed_files:
        # Normalize to POSIX
        normalized = Path(filepath).as_posix()

        # Check against allowlist
        if _matches_allowlist(normalized, allowlist):
            allowed.append(normalized)
        else:
            disallowed.append(normalized)

    return allowed, disallowed


def _matches_allowlist(filepath: str, allowlist: list[str]) -> bool:
    """Check if filepath matches any allowlist pattern."""
    # Normalize filepath
    normalized = filepath.strip()

    for pattern in allowlist:
        # Normalize pattern (strip backticks, whitespace)
        clean_pattern = pattern.strip().strip("`")

        # Exact match
        if normalized == clean_pattern:
            return True

        # Glob match
        if fnmatch(normalized, clean_pattern):
            return True

    return False


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


def _compute_diff_hash(allowed: list[str], disallowed: list[str]) -> str:
    """Compute deterministic hash of file lists."""
    # Create canonical string
    canonical = "\n".join(
        sorted(allowed) + ["---"] + sorted(disallowed)
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _write_allowlist_diff_json(
    result: AllowlistDiff,
    out_dir: Path,
    repo_root: Path,
    timestamp_mode: str
) -> None:
    """Write ALLOWLIST_DIFF.json."""
    timestamp = (
        "1970-01-01T00:00:00Z" if timestamp_mode == "deterministic"
        else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    data = {
        "schema_version": "1.0",
        "pipeline_version": CHATX_VERSION,
        "run_id": result.run_id,
        "generated_at": timestamp,
        "timestamp_mode": timestamp_mode,
        "repo_root": str(repo_root),
        "task_packet": {
            "id": result.task_id,
            "title": result.task_title,
            "allowlist": result.allowlist
        },
        "diff_mode_used": result.diff_mode_used,
        "changed_files": {
            "allowed": result.allowed_files,
            "disallowed": result.disallowed_files
        },
        "violations": {
            "count": len(result.violations),
            "items": [
                {
                    "type": v.type,
                    "message": v.message,
                    "files": v.files
                }
                for v in result.violations
            ]
        },
        "hashes": {
            "diff_hash": result.diff_hash
        }
    }

    output_path = out_dir / "ALLOWLIST_DIFF.json"
    write_json_strict(
        data=data,
        output_path=output_path,
        schema_name="allowlist_diff"
    )


def _write_violations_md(
    result: AllowlistDiff,
    out_dir: Path,
    diff_mode: str
) -> None:
    """Write VIOLATIONS.md."""
    status = "PASS ✓" if not result.violations else f"FAIL ✗ ({len(result.violations)} violations)"

    lines = [
        "# Allowlist Compliance Report",
        "",
        f"**Status:** {status}",
        f"**Run ID:** {result.run_id}",
        f"**Task:** {result.task_id} — {result.task_title}",
        f"**Diff Mode:** {diff_mode}",
        "",
        "## Allowed Changed Files",
        ""
    ]

    if result.allowed_files:
        for filepath in result.allowed_files:
            lines.append(f"- ✓ `{filepath}`")
    else:
        lines.append("*(none)*")

    lines.extend([
        "",
        "## Disallowed Changed Files",
        ""
    ])

    if result.disallowed_files:
        for filepath in result.disallowed_files:
            lines.append(f"- ✗ `{filepath}`")
    else:
        lines.append("*(none)*")

    if result.violations:
        lines.extend([
            "",
            "## Violations",
            ""
        ])

        for i, violation in enumerate(result.violations, 1):
            lines.append(f"### {i}. {violation.type}")
            lines.append(f"**Message:** {violation.message}")
            if violation.files:
                lines.append("**Files:**")
                for filepath in violation.files:
                    lines.append(f"- `{filepath}`")
            lines.append("")

    output_path = out_dir / "VIOLATIONS.md"
    output_path.write_text("\n".join(lines))
