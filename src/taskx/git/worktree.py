"""Worktree orchestration for TaskX commit sequencing flows."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from taskx.obs.run_artifacts import DIRTY_STATE_FILENAME, WORKTREE_FILENAME

VALID_DIRTY_POLICIES = {"refuse", "stash"}


def get_timestamp() -> str:
    """Return wallclock timestamp for generated artifacts."""
    return datetime.now(UTC).isoformat()


def run_git_command(args: list[str], cwd: Path) -> str:
    """Run a git command and return stdout text."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Git command failed in {cwd}: git {' '.join(args)}\n{exc.stderr.strip()}"
        ) from exc
    return result.stdout.strip()


def parse_status_output(status_output: str) -> list[str]:
    """Parse git porcelain status output into repository-relative paths."""
    changed_files: list[str] = []
    for raw_line in status_output.splitlines():
        if not raw_line:
            continue
        path_fragment = raw_line[3:]
        if " -> " in path_fragment:
            path_fragment = path_fragment.split(" -> ", 1)[1]
        if path_fragment.startswith('"') and path_fragment.endswith('"'):
            path_fragment = path_fragment[1:-1]
        changed_files.append(path_fragment)
    return changed_files


def git_changed_files(cwd: Path) -> list[str]:
    """Return changed file paths from git status porcelain output."""
    status_output = run_git_command(
        ["status", "--porcelain", "--untracked-files=all"],
        cwd=cwd,
    )
    return parse_status_output(status_output)


def git_staged_files(cwd: Path) -> list[str]:
    """Return staged files from the git index."""
    staged_output = run_git_command(["diff", "--cached", "--name-only"], cwd=cwd)
    return [line.strip() for line in staged_output.splitlines() if line.strip()]


def append_dirty_state_entry(run_dir: Path, entry: dict[str, Any]) -> dict[str, Any]:
    """Append a dirty-state entry into DIRTY_STATE.json."""
    path = run_dir / DIRTY_STATE_FILENAME
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "run_dir": str(run_dir.resolve()),
        "events": [],
    }

    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                payload.update(existing)
        except json.JSONDecodeError:
            pass

    events = payload.get("events")
    if not isinstance(events, list):
        events = []
    events.append(entry)
    payload["events"] = events
    path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")
    return payload


def stash_changes(
    *,
    cwd: Path,
    message: str,
    include_untracked: bool = True,
    paths: list[str] | None = None,
) -> str:
    """Stash changes and return git stash command output."""
    args = ["stash", "push"]
    if include_untracked:
        args.append("-u")
    args.extend(["-m", message])
    if paths:
        args.append("--")
        args.extend(paths)
    return run_git_command(args, cwd=cwd)


def start_worktree(
    run_dir: Path,
    repo_root: Path,
    *,
    base_branch: str = "main",
    remote: str = "origin",
    branch: str | None,
    worktree_path: Path | None,
    dirty_policy: str = "refuse",
) -> dict[str, Any]:
    """Create a task branch worktree and write WORKTREE.json artifact."""
    errors: list[str] = []
    resolved_run_dir = run_dir.resolve()
    resolved_repo_root = repo_root.resolve()
    resolved_branch = branch or f"taskx/{resolved_run_dir.name.lower()}"
    resolved_worktree_path = (
        worktree_path.resolve()
        if worktree_path is not None
        else (resolved_repo_root / "out" / "worktrees" / resolved_branch.replace("/", "__")).resolve()
    )

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": get_timestamp(),
        "run_dir": str(resolved_run_dir),
        "repo_root": str(resolved_repo_root),
        "status": "failed",
        "errors": errors,
        "dirty_policy": dirty_policy,
        "dirty_handling": {
            "had_dirty_state": False,
            "stashed": False,
            "stash_message": None,
            "stash_output": None,
            "changed_files": [],
        },
        "worktree": {
            "base_branch": base_branch,
            "remote": remote,
            "branch": resolved_branch,
            "worktree_path": str(resolved_worktree_path),
        },
    }

    try:
        if dirty_policy not in VALID_DIRTY_POLICIES:
            raise RuntimeError(
                f"Unsupported dirty policy: {dirty_policy}. "
                f"Expected one of {sorted(VALID_DIRTY_POLICIES)}."
            )
        if not resolved_run_dir.exists():
            raise RuntimeError(f"Run directory does not exist: {resolved_run_dir}")
        if not resolved_repo_root.exists():
            raise RuntimeError(f"Repository root does not exist: {resolved_repo_root}")

        run_git_command(["fetch", remote], cwd=resolved_repo_root)

        dirty_files = sorted(set(git_changed_files(resolved_repo_root)))
        run_dir_relative: str | None = None
        try:
            run_dir_relative = resolved_run_dir.relative_to(resolved_repo_root).as_posix()
        except ValueError:
            run_dir_relative = None
        if run_dir_relative is not None:
            dirty_files = [
                path
                for path in dirty_files
                if path != run_dir_relative and not path.startswith(f"{run_dir_relative}/")
            ]

        if dirty_files:
            report["dirty_handling"]["had_dirty_state"] = True
            report["dirty_handling"]["changed_files"] = dirty_files
            if dirty_policy == "refuse":
                raise RuntimeError(
                    "Repository has uncommitted changes. "
                    "Use --dirty-policy stash to stash and continue."
                )
            stash_message = f"taskx:wt-start:{resolved_run_dir.name}"
            stash_output = stash_changes(
                cwd=resolved_repo_root,
                message=stash_message,
                include_untracked=True,
                paths=dirty_files,
            )
            report["dirty_handling"]["stashed"] = True
            report["dirty_handling"]["stash_message"] = stash_message
            report["dirty_handling"]["stash_output"] = stash_output
            append_dirty_state_entry(
                resolved_run_dir,
                {
                    "event": "worktree_start",
                    "policy": dirty_policy,
                    "action": "stash",
                    "scope": "repo_root",
                    "created_at": get_timestamp(),
                    "changed_files": dirty_files,
                    "stash_message": stash_message,
                    "stash_output": stash_output,
                },
            )

        branch_exists = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{resolved_branch}"],
            cwd=resolved_repo_root,
            check=False,
            capture_output=True,
            text=True,
        ).returncode == 0
        if branch_exists:
            raise RuntimeError(f"Branch already exists: {resolved_branch}")

        run_git_command(
            ["branch", resolved_branch, f"{remote}/{base_branch}"],
            cwd=resolved_repo_root,
        )

        resolved_worktree_path.parent.mkdir(parents=True, exist_ok=True)
        if resolved_worktree_path.exists():
            raise RuntimeError(f"Worktree path already exists: {resolved_worktree_path}")

        run_git_command(
            ["worktree", "add", str(resolved_worktree_path), resolved_branch],
            cwd=resolved_repo_root,
        )

        artifact_payload = {
            "schema_version": "1.0",
            "generated_at": get_timestamp(),
            "run_dir": str(resolved_run_dir),
            "repo_root": str(resolved_repo_root),
            "worktree_path": str(resolved_worktree_path),
            "branch": resolved_branch,
            "base_branch": base_branch,
            "remote": remote,
        }
        (resolved_run_dir / WORKTREE_FILENAME).write_text(
            f"{json.dumps(artifact_payload, indent=2, sort_keys=True)}\n",
            encoding="utf-8",
        )

        report["status"] = "passed"
        report["artifact"] = str((resolved_run_dir / WORKTREE_FILENAME).resolve())
        return report
    except Exception as exc:  # pragma: no cover - explicit failure path serialization
        errors.append(str(exc))
        return report
