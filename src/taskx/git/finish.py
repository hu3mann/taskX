"""Finish workflow for worktree-based TaskX runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from taskx.git.worktree import (
    VALID_DIRTY_POLICIES,
    append_dirty_state_entry,
    git_changed_files,
    run_git_command,
    stash_changes,
)
from taskx.obs.run_artifacts import FINISH_FILENAME, WORKTREE_FILENAME


def _clean_or_stash(
    *,
    run_dir: Path,
    cwd: Path,
    scope: str,
    dirty_policy: str,
    event: str,
    exclude_prefixes: list[str] | None = None,
) -> dict[str, Any]:
    changed_files = sorted(set(git_changed_files(cwd)))
    if exclude_prefixes:
        changed_files = [
            path
            for path in changed_files
            if not any(
                path == prefix or path.startswith(f"{prefix}/")
                for prefix in exclude_prefixes
            )
        ]
    summary: dict[str, Any] = {
        "scope": scope,
        "changed_files": changed_files,
        "stashed": False,
        "stash_message": None,
        "stash_output": None,
    }
    if not changed_files:
        return summary

    if dirty_policy == "refuse":
        raise RuntimeError(
            f"{scope} has uncommitted changes. "
            "Use --dirty-policy stash to stash and continue."
        )

    stash_message = f"taskx:finish:{run_dir.name}:{scope}"
    stash_output = stash_changes(
        cwd=cwd,
        message=stash_message,
        include_untracked=True,
    )
    summary["stashed"] = True
    summary["stash_message"] = stash_message
    summary["stash_output"] = stash_output
    append_dirty_state_entry(
        run_dir,
        {
            "event": event,
            "scope": scope,
            "policy": dirty_policy,
            "action": "stash",
            "changed_files": changed_files,
            "stash_message": stash_message,
            "stash_output": stash_output,
        },
    )
    return summary


def finish_run(
    run_dir: Path,
    *,
    mode: str = "rebase-ff",
    cleanup: bool = True,
    dirty_policy: str = "refuse",
    remote: str = "origin",
) -> dict[str, Any]:
    """Finish a run by rebasing and fast-forwarding main to the task branch."""
    resolved_run_dir = run_dir.resolve()
    report_path = resolved_run_dir / FINISH_FILENAME
    errors: list[str] = []
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "run_dir": str(resolved_run_dir),
        "status": "failed",
        "errors": errors,
        "mode": mode,
        "cleanup": cleanup,
        "dirty_policy": dirty_policy,
        "remote": remote,
        "worktree": {
            "repo_root": None,
            "worktree_path": None,
            "branch": None,
            "base_branch": None,
        },
        "hashes": {
            "task_branch_before_rebase": None,
            "task_branch_after_rebase": None,
            "main_before_pull": None,
            "main_after_pull": None,
            "main_after_merge": None,
            "origin_main_after_push": None,
        },
        "dirty_handling": {
            "worktree": None,
            "repo_root": None,
        },
        "verification": {
            "main_matches_remote": False,
            "local_main_hash": None,
            "origin_main_hash": None,
        },
    }

    try:
        if mode != "rebase-ff":
            raise RuntimeError(f"Unsupported finish mode: {mode}. Expected 'rebase-ff'.")
        if dirty_policy not in VALID_DIRTY_POLICIES:
            raise RuntimeError(
                f"Unsupported dirty policy: {dirty_policy}. "
                f"Expected one of {sorted(VALID_DIRTY_POLICIES)}."
            )

        worktree_artifact = resolved_run_dir / WORKTREE_FILENAME
        if not worktree_artifact.exists():
            raise RuntimeError(f"Required artifact missing: {worktree_artifact}")
        metadata = json.loads(worktree_artifact.read_text(encoding="utf-8"))

        repo_root = Path(metadata["repo_root"]).resolve()
        worktree_path = Path(metadata["worktree_path"]).resolve()
        task_branch = str(metadata["branch"])
        base_branch = str(metadata["base_branch"])

        if not worktree_path.exists():
            raise RuntimeError(f"Worktree path does not exist: {worktree_path}")
        if not repo_root.exists():
            raise RuntimeError(f"Repository root does not exist: {repo_root}")

        report["worktree"] = {
            "repo_root": str(repo_root),
            "worktree_path": str(worktree_path),
            "branch": task_branch,
            "base_branch": base_branch,
        }

        worktree_dirty = _clean_or_stash(
            run_dir=resolved_run_dir,
            cwd=worktree_path,
            scope="worktree",
            dirty_policy=dirty_policy,
            event="finish_worktree_preflight",
        )
        report["dirty_handling"]["worktree"] = worktree_dirty

        run_git_command(["fetch", remote], cwd=repo_root)

        report["hashes"]["task_branch_before_rebase"] = run_git_command(
            ["rev-parse", "HEAD"],
            cwd=worktree_path,
        )
        run_git_command(["rebase", f"{remote}/{base_branch}"], cwd=worktree_path)
        report["hashes"]["task_branch_after_rebase"] = run_git_command(
            ["rev-parse", "HEAD"],
            cwd=worktree_path,
        )

        run_dir_relative_to_repo: str | None = None
        worktree_relative_to_repo: str | None = None
        try:
            run_dir_relative_to_repo = resolved_run_dir.relative_to(repo_root).as_posix()
        except ValueError:
            run_dir_relative_to_repo = None
        try:
            worktree_relative_to_repo = worktree_path.relative_to(repo_root).as_posix()
        except ValueError:
            worktree_relative_to_repo = None

        exclude_prefixes = [
            prefix
            for prefix in [run_dir_relative_to_repo, worktree_relative_to_repo]
            if prefix
        ]

        repo_root_dirty = _clean_or_stash(
            run_dir=resolved_run_dir,
            cwd=repo_root,
            scope="repo_root",
            dirty_policy=dirty_policy,
            event="finish_repo_root_preflight",
            exclude_prefixes=exclude_prefixes or None,
        )
        report["dirty_handling"]["repo_root"] = repo_root_dirty

        current_branch = run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
        )
        if current_branch != base_branch:
            run_git_command(["checkout", base_branch], cwd=repo_root)

        report["hashes"]["main_before_pull"] = run_git_command(
            ["rev-parse", base_branch],
            cwd=repo_root,
        )
        run_git_command(["pull", "--ff-only", remote, base_branch], cwd=repo_root)
        report["hashes"]["main_after_pull"] = run_git_command(
            ["rev-parse", base_branch],
            cwd=repo_root,
        )

        run_git_command(["merge", "--ff-only", task_branch], cwd=repo_root)
        report["hashes"]["main_after_merge"] = run_git_command(
            ["rev-parse", base_branch],
            cwd=repo_root,
        )

        run_git_command(["push", remote, base_branch], cwd=repo_root)
        origin_main_hash = run_git_command(
            ["rev-parse", f"{remote}/{base_branch}"],
            cwd=repo_root,
        )
        local_main_hash = run_git_command(["rev-parse", base_branch], cwd=repo_root)
        report["hashes"]["origin_main_after_push"] = origin_main_hash
        report["verification"]["origin_main_hash"] = origin_main_hash
        report["verification"]["local_main_hash"] = local_main_hash
        report["verification"]["main_matches_remote"] = local_main_hash == origin_main_hash

        if local_main_hash != origin_main_hash:
            raise RuntimeError("Post-push verification failed: local main != origin/main.")

        if cleanup:
            run_git_command(
                ["worktree", "remove", str(worktree_path), "--force"],
                cwd=repo_root,
            )
            run_git_command(["branch", "-D", task_branch], cwd=repo_root)

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
                errors.append(f"Failed to write {FINISH_FILENAME}: {write_error}")
