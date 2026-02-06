"""Git commit operations for TaskX runs with allowlist enforcement."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


from typing import Any


def _get_timestamp(mode: str = "deterministic") -> str:
    """Get timestamp based on mode."""
    if mode == "deterministic":
        return "1970-01-01T00:00:00Z"
    return datetime.now(UTC).isoformat()


def _run_git_command(args: list[str], cwd: Path | None = None) -> str:
    """Run git command and return output.

    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory for command

    Returns:
        Command output (stdout)

    Raises:
        RuntimeError: If command fails
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: {' '.join(args)}\n{e.stderr}") from e


def commit_run(
    run_dir: Path,
    message: str | None = None,
    allow_unpromoted: bool = False,
    timestamp_mode: str = "deterministic",
) -> dict[str, Any]:
    """Create a git commit for a completed TaskX run.

    Only stages files that are:
    1. In the allowlist (from ALLOWLIST_DIFF.json)
    2. Actually modified (per git status)

    Refuses to commit if:
    - Allowlist violations exist
    - Run is not promoted (unless allow_unpromoted=True)
    - Not in a git repository

    Args:
        run_dir: Path to run directory
        message: Optional custom commit message
        allow_unpromoted: Allow commit without promotion token
        timestamp_mode: "deterministic" or "wallclock"

    Returns:
        Report dict with commit details

    Raises:
        RuntimeError: If validation fails or git operations fail
    """
    errors: list[str] = []
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": _get_timestamp(timestamp_mode),
        "timestamp_mode": timestamp_mode,
        "run_dir": str(run_dir.resolve()),
        "repo_root": "",
        "git": {
            "branch": "",
            "head_before": "",
            "head_after": None,
            "commit_created": False,
            "commit_message": None,
        },
        "allowlist": {
            "allowed_files": [],
            "staged_files": [],
            "disallowed_files_detected": [],
            "violations_count": 0,
        },
        "promotion": {
            "required": not allow_unpromoted,
            "found": False,
            "token_path": None,
            "token_id": None,
        },
        "status": "failed",
        "errors": errors,
    }

    # 1. Validate run_dir exists
    if not run_dir.exists():
        errors.append(f"Run directory does not exist: {run_dir}")
        return report

    # 2. Load allowlist results
    allowlist_path = run_dir / "ALLOWLIST_DIFF.json"
    if not allowlist_path.exists():
        errors.append(f"Allowlist report not found: {allowlist_path}")
        errors.append("Run 'taskx gate-allowlist' first to generate allowlist report")
        return report

    try:
        with open(allowlist_path) as f:
            allowlist_data = json.load(f)
    except Exception as e:
        errors.append(f"Failed to parse allowlist report: {e}")
        return report

    # 3. Check for allowlist violations
    violations = allowlist_data.get("violations", [])
    allowed_files = allowlist_data.get("allowed_files", [])

    if violations:
        report["allowlist"]["violations_count"] = len(violations)
        report["allowlist"]["disallowed_files_detected"] = [
            v.get("path", "unknown") for v in violations
        ]
        errors.append(f"Allowlist has {len(violations)} violation(s)")
        errors.append("Fix violations or update allowlist before committing")
        return report

    report["allowlist"]["allowed_files"] = allowed_files

    # 4. Check promotion token
    promotion_path = run_dir / "PROMOTION.json"
    if promotion_path.exists():
        report["promotion"]["found"] = True
        report["promotion"]["token_path"] = str(promotion_path)

        try:
            with open(promotion_path) as f:
                promo_data = json.load(f)
                report["promotion"]["token_id"] = promo_data.get("token", "unknown")
        except Exception:
            pass  # Token path exists but can't read - continue anyway

    if not report["promotion"]["found"] and not allow_unpromoted:
        errors.append("Run is not promoted (no PROMOTION.json found)")
        errors.append("Either run 'taskx promote-run' or use --allow-unpromoted")
        return report

    # 5. Confirm we're in a git repo
    try:
        # Start git repo search from run directory
        repo_root = Path(_run_git_command(
            ["rev-parse", "--show-toplevel"],
            cwd=run_dir
        ))
        report["repo_root"] = str(repo_root)
    except RuntimeError as e:
        errors.append(f"Not in a git repository: {e}")
        return report

    # Get current branch and HEAD
    try:
        branch = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
        head_before = _run_git_command(["rev-parse", "HEAD"], cwd=repo_root)
        report["git"]["branch"] = branch
        report["git"]["head_before"] = head_before
    except RuntimeError as e:
        errors.append(f"Failed to get git status: {e}")
        return report

    # 6. Get modified files from git status
    try:
        status_output = _run_git_command(
            ["status", "--porcelain", "--untracked-files=all"],
            cwd=repo_root
        )
    except RuntimeError as e:
        errors.append(f"Failed to get git status: {e}")
        return report

    # Parse status output to get modified files
    modified_files = set()
    for line in status_output.splitlines():
        if not line:
            continue
        # Format: "XY filename" where X is staged, Y is unstaged
        status_code = line[:2]
        filepath = line[3:]

        # Skip deleted files
        if 'D' in status_code:
            continue

        modified_files.add(filepath)

    # 7. Stage only allowed files that are modified
    files_to_stage = []
    for allowed_file in allowed_files:
        # Convert to relative path from repo root
        try:
            rel_path = Path(allowed_file).relative_to(repo_root)
            rel_path_str = str(rel_path)
        except (ValueError, TypeError):
            # Already relative or invalid path
            rel_path_str = allowed_file

        if rel_path_str in modified_files:
            files_to_stage.append(rel_path_str)

    if not files_to_stage:
        errors.append("No modified files to stage from allowlist")
        errors.append("Either no changes were made or files are already committed")
        return report

    # Stage the files
    try:
        for filepath in files_to_stage:
            _run_git_command(["add", "--", filepath], cwd=repo_root)
        report["allowlist"]["staged_files"] = files_to_stage
    except RuntimeError as e:
        errors.append(f"Failed to stage files: {e}")
        return report

    # 8. Create commit message
    if message is None:
        run_name = run_dir.name
        promo_token = report["promotion"].get("token_id", "NONE")
        message = f"TASKX commit-run | run={run_name} | promo={promo_token}"

    report["git"]["commit_message"] = message

    # Create commit
    try:
        _run_git_command(["commit", "-m", message], cwd=repo_root)
        head_after = _run_git_command(["rev-parse", "HEAD"], cwd=repo_root)

        report["git"]["head_after"] = head_after
        report["git"]["commit_created"] = True
        report["status"] = "passed"

    except RuntimeError as e:
        errors.append(f"Failed to create commit: {e}")
        return report

    # 9. Write report to run directory
    report_path = run_dir / "COMMIT_RUN.json"
    try:
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, sort_keys=True)
    except Exception as e:
        # Non-fatal - commit was created, just couldn't write report
        errors.append(f"Warning: Failed to write report: {e}")

    return report
