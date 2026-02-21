"""Fail-closed guards for taskx tp git commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from taskx.ops.tp_git.exec import ExecError, ExecResult, run_git


@dataclass(frozen=True)
class DoctorReport:
    """Structured doctor result for downstream command flows."""

    repo_root: Path
    branch: str
    status_porcelain: str
    stash_list: str
    fetch: ExecResult
    pull: ExecResult


def resolve_repo_root(repo: Path | None = None) -> Path:
    """Resolve git repo root from cwd or explicit path."""
    probe = (repo or Path.cwd()).resolve()
    try:
        out = run_git(["rev-parse", "--show-toplevel"], repo_root=probe)
    except ExecError as exc:
        raise RuntimeError(f"unable to resolve git repo root from {probe}: {exc}") from exc
    root = out.stdout.strip()
    if not root:
        raise RuntimeError(f"unable to resolve git repo root from {probe}: empty output")
    return Path(root).resolve()


def run_doctor(
    *,
    repo: Path | None = None,
) -> DoctorReport:
    """Enforce clean-main+no-stash gate and sync remote refs."""
    repo_root = resolve_repo_root(repo)

    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root=repo_root).stdout.strip()
    if branch != "main":
        raise RuntimeError(f"doctor failed: expected branch main, found {branch}")

    status_porcelain = run_git(["status", "--porcelain"], repo_root=repo_root).stdout
    if status_porcelain.strip():
        raise RuntimeError("doctor failed: main has uncommitted changes (git status --porcelain is non-empty)")

    stash_list = run_git(["stash", "list"], repo_root=repo_root).stdout
    if stash_list.strip():
        raise RuntimeError("doctor failed: git stash list is non-empty; stash workflow is forbidden")

    fetch = run_git(["fetch", "--all", "--prune"], repo_root=repo_root)
    pull = run_git(["pull", "--ff-only"], repo_root=repo_root)

    return DoctorReport(
        repo_root=repo_root,
        branch=branch,
        status_porcelain=status_porcelain,
        stash_list=stash_list,
        fetch=fetch,
        pull=pull,
    )
