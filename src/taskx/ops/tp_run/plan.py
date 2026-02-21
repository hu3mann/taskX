"""Deterministic stage runner for taskx tp run."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from taskx.ops.tp_git.exec import run_git
from taskx.ops.tp_git.git_worktree import start_tp
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


@dataclass(frozen=True)
class RunResult:
    """Outcome envelope for tp run orchestration."""

    exit_code: int
    message: str
    branch: str | None
    worktree_path: Path | None


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

    writer.write_json(
        "EXIT.json",
        {
            "exit_code": 0,
            "reason": "start complete; continue with --continue or tp git pr/merge",
            "run_id": options.run_id,
        },
    )
    return RunResult(
        exit_code=0,
        message=banner,
        branch=branch,
        worktree_path=worktree_path,
    )
