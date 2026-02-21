"""Deterministic stage runner for taskx tp run."""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from taskx.ops.tp_git.exec import run_git
from taskx.ops.tp_git.git_worktree import cleanup_tp, start_tp, sync_main
from taskx.ops.tp_git.github import merge_pr, pr_create, pr_status
from taskx.ops.tp_git.guards import run_doctor
from taskx.ops.tp_git.naming import build_worktree_path, normalize_slug, resolve_target
from taskx.ops.tp_run.proof import ProofWriter

StopAfter = Literal["doctor", "start", "test", "pr", "merge", "sync", "cleanup"]


@dataclass(frozen=True)
class RunOptions:
    """Inputs for the tp run orchestration."""

    repo_root: Path
    tp_id: str
    slug: str
    run_id: str
    continue_mode: bool = False
    stop_after: StopAfter | None = None
    test_cmd: str | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    pr_body_file: Path | None = None
    wait_merge: bool = False
    wait_timeout_sec: int = 900
    merge_enabled: bool = True


@dataclass(frozen=True)
class RunResult:
    """Outcome envelope for tp run orchestration."""

    exit_code: int
    message: str
    branch: str | None
    worktree_path: Path | None
    merged_confirmed: bool = False


def _capture_precheck(repo_root: Path) -> str:
    lines: list[str] = []
    checks = [
        ["rev-parse", "--abbrev-ref", "HEAD"],
        ["status", "--porcelain"],
        ["stash", "list"],
        ["fetch", "--all", "--prune"],
        ["pull", "--ff-only"],
    ]
    for args in checks:
        rendered = "git " + " ".join(args)
        result = run_git(args, repo_root=repo_root, check=False)
        lines.append(f"$ {rendered}")
        lines.append(result.stdout.rstrip())
        if result.stderr.strip():
            lines.append(result.stderr.rstrip())
        lines.append(f"[exit={result.returncode}]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_banner(*, worktree_path: Path, branch: str) -> str:
    return (
        "Task Packet work banner\n"
        f"- worktree: {worktree_path}\n"
        f"- branch: {branch}\n"
        "Do work in this worktree. Commit per TP commit plan.\n"
        "Then rerun `taskx tp run ... --continue` or use `taskx tp git pr/merge`.\n"
    )


def execute_run(options: RunOptions, writer: ProofWriter) -> RunResult:
    """Execute deterministic tp run stages up through start/banner."""
    repo_root = options.repo_root
    normalized_slug = normalize_slug(options.slug)
    started_at = datetime.now(UTC).isoformat()

    writer.write_text("PRECHECK.txt", _capture_precheck(repo_root))

    if not options.continue_mode:
        try:
            doctor = run_doctor(repo=repo_root)
        except RuntimeError as exc:
            writer.write_json(
                "EXIT.json",
                {"exit_code": 1, "reason": str(exc), "stage": "doctor", "run_id": options.run_id},
            )
            writer.write_json(
                "RUN.json",
                {
                    "tp_id": options.tp_id,
                    "slug": normalized_slug,
                    "run_id": options.run_id,
                    "repo_root": str(repo_root),
                    "branch": None,
                    "worktree_path": None,
                    "start_time": started_at,
                    "end_time": datetime.now(UTC).isoformat(),
                },
            )
            return RunResult(exit_code=1, message=str(exc), branch=None, worktree_path=None)

        if options.stop_after == "doctor":
            writer.write_json("EXIT.json", {"exit_code": 0, "reason": "stopped after doctor", "run_id": options.run_id})
            writer.write_json(
                "RUN.json",
                {
                    "tp_id": options.tp_id,
                    "slug": normalized_slug,
                    "run_id": options.run_id,
                    "repo_root": str(repo_root),
                    "branch": None,
                    "worktree_path": None,
                    "start_time": started_at,
                    "end_time": datetime.now(UTC).isoformat(),
                    "doctor_branch": doctor.branch,
                },
            )
            return RunResult(exit_code=0, message="stopped after doctor", branch=None, worktree_path=None)

        try:
            started = start_tp(tp_id=options.tp_id, slug=normalized_slug, repo=repo_root, reuse=False)
        except RuntimeError as exc:
            writer.write_json(
                "EXIT.json",
                {"exit_code": 1, "reason": str(exc), "stage": "start", "run_id": options.run_id},
            )
            writer.write_json(
                "RUN.json",
                {
                    "tp_id": options.tp_id,
                    "slug": normalized_slug,
                    "run_id": options.run_id,
                    "repo_root": str(repo_root),
                    "branch": None,
                    "worktree_path": None,
                    "start_time": started_at,
                    "end_time": datetime.now(UTC).isoformat(),
                },
            )
            return RunResult(exit_code=1, message=str(exc), branch=None, worktree_path=None)

        worktree_path = started.worktree_path
        branch = started.branch
    else:
        target = resolve_target(repo_root=repo_root, tp_id=options.tp_id, slug=normalized_slug)
        worktree_path = build_worktree_path(repo_root, options.tp_id)
        branch = target.branch

    worktree_listing = run_git(["worktree", "list"], repo_root=repo_root, check=False).stdout
    writer.write_text("WORKTREE.txt", worktree_listing)

    status_before = run_git(["-C", str(worktree_path), "status", "--porcelain"], repo_root=repo_root, check=False)
    writer.write_text("STATUS_BEFORE.txt", status_before.stdout)

    banner = _render_banner(worktree_path=worktree_path, branch=branch)
    writer.write_text("BANNER.txt", banner)

    writer.write_json(
        "RUN.json",
        {
            "tp_id": options.tp_id,
            "slug": normalized_slug,
            "run_id": options.run_id,
            "repo_root": str(repo_root),
            "branch": branch,
            "worktree_path": str(worktree_path),
            "start_time": started_at,
            "end_time": datetime.now(UTC).isoformat(),
            "git_shas": {
                "main_before": run_git(["rev-parse", "HEAD"], repo_root=repo_root).stdout.strip(),
                "worktree_head": run_git(["-C", str(worktree_path), "rev-parse", "HEAD"], repo_root=repo_root).stdout.strip(),
            },
        },
    )

    if options.stop_after == "start":
        writer.write_json("EXIT.json", {"exit_code": 0, "reason": "stopped after start", "run_id": options.run_id})
        return RunResult(exit_code=0, message=banner, branch=branch, worktree_path=worktree_path)

    if options.test_cmd:
        argv = shlex.split(options.test_cmd)
        completed = subprocess.run(argv, cwd=worktree_path, capture_output=True, text=True, check=False)
        tests_log = (
            f"$ {options.test_cmd}\n"
            f"{completed.stdout}"
            f"{completed.stderr}"
            f"\n[exit={completed.returncode}]\n"
        )
        writer.write_text("TESTS.txt", tests_log)
        if completed.returncode != 0:
            writer.write_json(
                "EXIT.json",
                {
                    "exit_code": completed.returncode,
                    "reason": "test command failed",
                    "stage": "test",
                    "run_id": options.run_id,
                },
            )
            return RunResult(
                exit_code=completed.returncode,
                message="test command failed",
                branch=branch,
                worktree_path=worktree_path,
            )
        if options.stop_after == "test":
            writer.write_json("EXIT.json", {"exit_code": 0, "reason": "stopped after test", "run_id": options.run_id})
            return RunResult(exit_code=0, message="stopped after test", branch=branch, worktree_path=worktree_path)

    title = options.pr_title or f"{options.tp_id}: {normalized_slug}"
    body = options.pr_body or (
        "Automated TaskX TP run.\n\n"
        f"- run_id: {options.run_id}\n"
        f"- proof_dir: {writer.paths.run_dir}\n"
        "- checklist: tests passed, PR opened by taskx tp run\n"
    )
    try:
        pr_payload = pr_create(
            tp_id=options.tp_id,
            title=title,
            body=body if options.pr_body_file is None else None,
            body_file=options.pr_body_file,
            repo=repo_root,
        )
    except RuntimeError as exc:
        writer.write_json(
            "EXIT.json",
            {"exit_code": 1, "reason": str(exc), "stage": "pr", "run_id": options.run_id},
        )
        return RunResult(exit_code=1, message=str(exc), branch=branch, worktree_path=worktree_path)

    writer.write_json("PR.json", pr_payload)
    if options.stop_after == "pr":
        writer.write_json("EXIT.json", {"exit_code": 0, "reason": "stopped after pr", "run_id": options.run_id})
        return RunResult(exit_code=0, message="stopped after pr", branch=branch, worktree_path=worktree_path)

    merged_confirmed = str(pr_payload.get("state", "")).upper() == "MERGED"
    merge_payload: dict[str, object] | None = None
    if options.merge_enabled:
        try:
            merge_payload = merge_pr(tp_id=options.tp_id, mode="squash", repo=repo_root)
        except RuntimeError as exc:
            writer.write_json(
                "EXIT.json",
                {"exit_code": 1, "reason": str(exc), "stage": "merge", "run_id": options.run_id},
            )
            writer.write_json("MERGE.json", {"error": str(exc), "run_id": options.run_id})
            return RunResult(exit_code=1, message=str(exc), branch=branch, worktree_path=worktree_path)

        writer.write_json("MERGE.json", merge_payload)
        merged_confirmed = str(merge_payload.get("state", "")).upper() == "MERGED"
        if options.stop_after == "merge":
            writer.write_json("EXIT.json", {"exit_code": 0, "reason": "stopped after merge", "run_id": options.run_id})
            return RunResult(
                exit_code=0,
                message="stopped after merge",
                branch=branch,
                worktree_path=worktree_path,
                merged_confirmed=merged_confirmed,
            )

    if options.wait_merge:
        deadline = time.time() + options.wait_timeout_sec
        while time.time() < deadline:
            status_payload = pr_status(tp_id=options.tp_id, repo=repo_root)
            pr_obj = status_payload.get("pr")
            if isinstance(pr_obj, dict):
                state = str(pr_obj.get("state", "")).upper()
                writer.write_json("PR.json", pr_obj)
                if state == "MERGED":
                    merged_confirmed = True
                    break
            time.sleep(5)

        if not merged_confirmed:
            writer.write_json(
                "EXIT.json",
                {
                    "exit_code": 1,
                    "reason": "wait-merge timed out before merged state",
                    "stage": "wait",
                    "run_id": options.run_id,
                },
            )
            return RunResult(
                exit_code=1,
                message="wait-merge timed out before merged state",
                branch=branch,
                worktree_path=worktree_path,
                merged_confirmed=False,
            )

    if not merged_confirmed:
        writer.write_json(
            "EXIT.json",
            {
                "exit_code": 1,
                "reason": "merge not confirmed; sync-main and cleanup skipped",
                "stage": "merge-check",
                "run_id": options.run_id,
            },
        )
        return RunResult(
            exit_code=1,
            message="merge not confirmed; run with --wait-merge or complete merge manually",
            branch=branch,
            worktree_path=worktree_path,
            merged_confirmed=False,
        )

    sync_payload = sync_main(repo=repo_root)
    writer.write_text(
        "SYNC_MAIN.txt",
        (
            f"repo_root={sync_payload['repo_root']}\n"
            f"fetch={sync_payload['fetch']}\n"
            f"pull={sync_payload['pull']}\n"
        ),
    )
    if options.stop_after == "sync":
        writer.write_json("EXIT.json", {"exit_code": 0, "reason": "stopped after sync", "run_id": options.run_id})
        return RunResult(
            exit_code=0,
            message="stopped after sync",
            branch=branch,
            worktree_path=worktree_path,
            merged_confirmed=True,
        )

    cleanup_payload = cleanup_tp(tp_id=options.tp_id, repo=repo_root)
    writer.write_text(
        "CLEANUP.txt",
        (
            f"repo_root={cleanup_payload['repo_root']}\n"
            f"worktree_path={cleanup_payload['worktree_path']}\n"
            f"remove={cleanup_payload['remove']}\n"
            f"prune={cleanup_payload['prune']}\n"
        ),
    )
    if options.stop_after == "cleanup":
        writer.write_json("EXIT.json", {"exit_code": 0, "reason": "stopped after cleanup", "run_id": options.run_id})
        return RunResult(
            exit_code=0,
            message="stopped after cleanup",
            branch=branch,
            worktree_path=Path(cleanup_payload["worktree_path"]),
            merged_confirmed=True,
        )

    writer.write_json(
        "EXIT.json",
        {
            "exit_code": 0,
            "reason": "run completed",
            "run_id": options.run_id,
        },
    )
    return RunResult(
        exit_code=0,
        message=banner,
        branch=branch,
        worktree_path=worktree_path,
        merged_confirmed=merged_confirmed,
    )
