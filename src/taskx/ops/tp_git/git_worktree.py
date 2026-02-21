"""Worktree lifecycle helpers for taskx tp git commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from taskx.ops.tp_git.exec import run_git
from taskx.ops.tp_git.guards import DoctorReport, resolve_repo_root, run_doctor
from taskx.ops.tp_git.naming import resolve_target


@dataclass(frozen=True)
class StartResult:
    """Start command outcome."""

    doctor: DoctorReport
    branch: str
    worktree_path: Path
    reused: bool


def _worktree_branch(repo_root: Path, worktree_path: Path) -> str | None:
    listing = run_git(["worktree", "list", "--porcelain"], repo_root=repo_root).stdout
    target = str(worktree_path.resolve())
    active_path: str | None = None
    active_branch: str | None = None
    for raw_line in listing.splitlines():
        line = raw_line.strip()
        if line.startswith("worktree "):
            active_path = line.split(" ", 1)[1]
            active_branch = None
            continue
        if line.startswith("branch "):
            active_branch = line.split(" ", 1)[1].removeprefix("refs/heads/")
            continue
        if not line and active_path == target:
            return active_branch
    if active_path == target:
        return active_branch
    return None


def _ensure_branch_absent(repo_root: Path, branch: str) -> None:
    result = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], repo_root=repo_root, check=False)
    if result.returncode == 0:
        raise RuntimeError(f"start failed: branch already exists: {branch}")


def start_tp(
    *,
    tp_id: str,
    slug: str,
    repo: Path | None = None,
    reuse: bool = False,
) -> StartResult:
    """Run doctor and create deterministic branch/worktree."""
    doctor = run_doctor(repo=repo)
    repo_root = doctor.repo_root
    target = resolve_target(repo_root=repo_root, tp_id=tp_id, slug=slug)

    target.worktree_path.parent.mkdir(parents=True, exist_ok=True)

    if target.worktree_path.exists():
        if not reuse:
            raise RuntimeError(
                f"start failed: worktree already exists at {target.worktree_path}; pass --reuse to validate reuse"
            )
        active_branch = _worktree_branch(repo_root, target.worktree_path)
        if active_branch != target.branch:
            raise RuntimeError(
                f"start failed: existing worktree branch mismatch (expected {target.branch}, found {active_branch})"
            )
        status = run_git(["-C", str(target.worktree_path), "status", "--porcelain"], repo_root=repo_root).stdout
        if status.strip():
            raise RuntimeError("start failed: --reuse refused because existing worktree is dirty")
        return StartResult(
            doctor=doctor,
            branch=target.branch,
            worktree_path=target.worktree_path,
            reused=True,
        )

    _ensure_branch_absent(repo_root, target.branch)
    run_git(
        ["worktree", "add", "-b", target.branch, str(target.worktree_path), "main"],
        repo_root=repo_root,
    )

    return StartResult(
        doctor=doctor,
        branch=target.branch,
        worktree_path=target.worktree_path,
        reused=False,
    )


def tp_status(*, tp_id: str, repo: Path | None = None) -> dict[str, str]:
    """Lightweight local status for a TP worktree."""
    repo_root = resolve_repo_root(repo)
    worktree_path = (repo_root / ".worktrees" / tp_id).resolve()
    if not worktree_path.exists():
        raise RuntimeError(f"status failed: worktree does not exist: {worktree_path}")

    branch = run_git(["-C", str(worktree_path), "rev-parse", "--abbrev-ref", "HEAD"], repo_root=repo_root).stdout.strip()
    status = run_git(["-C", str(worktree_path), "status", "--porcelain"], repo_root=repo_root).stdout
    return {
        "repo_root": str(repo_root),
        "worktree_path": str(worktree_path),
        "branch": branch,
        "dirty": "yes" if status.strip() else "no",
    }


def sync_main(*, repo: Path | None = None) -> dict[str, str]:
    """Sync main branch with ff-only policy."""
    repo_root = resolve_repo_root(repo)
    run_git(["checkout", "main"], repo_root=repo_root)
    fetch = run_git(["fetch", "--all", "--prune"], repo_root=repo_root)
    pull = run_git(["pull", "--ff-only"], repo_root=repo_root)
    return {
        "repo_root": str(repo_root),
        "fetch": (fetch.stdout.strip() or fetch.stderr.strip() or "(no output)"),
        "pull": (pull.stdout.strip() or pull.stderr.strip() or "(no output)"),
    }


def cleanup_tp(*, tp_id: str, repo: Path | None = None) -> dict[str, str]:
    """Remove TP worktree after validating cleanliness."""
    repo_root = resolve_repo_root(repo)
    worktree_path = (repo_root / ".worktrees" / tp_id).resolve()
    if not worktree_path.exists():
        raise RuntimeError(f"cleanup failed: worktree does not exist: {worktree_path}")

    status = run_git(["-C", str(worktree_path), "status", "--porcelain"], repo_root=repo_root).stdout
    if status.strip():
        raise RuntimeError("cleanup failed: worktree is dirty")

    remove = run_git(["worktree", "remove", str(worktree_path)], repo_root=repo_root)
    prune = run_git(["worktree", "prune"], repo_root=repo_root)
    return {
        "repo_root": str(repo_root),
        "worktree_path": str(worktree_path),
        "remove": (remove.stdout.strip() or remove.stderr.strip() or "(no output)"),
        "prune": (prune.stdout.strip() or prune.stderr.strip() or "(no output)"),
    }


def list_worktrees(*, repo: Path | None = None) -> str:
    """Return git worktree list output."""
    repo_root = resolve_repo_root(repo)
    listing = run_git(["worktree", "list"], repo_root=repo_root).stdout.rstrip()
    return listing
