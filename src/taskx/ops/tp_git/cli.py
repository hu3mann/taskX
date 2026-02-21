"""CLI surface for taskx tp git workflows."""

from __future__ import annotations

from pathlib import Path

import typer

from taskx.ops.tp_git.guards import run_doctor
from taskx.ops.tp_git.git_worktree import start_tp

app = typer.Typer(
    name="git",
    help="Task Packet git workflow commands",
    no_args_is_help=True,
)


@app.command("doctor")
def doctor(
    repo: Path | None = typer.Option(
        None,
        "--repo",
        help="Repository path (defaults to current working directory).",
    ),
) -> None:
    """Fail-closed gate: clean main, no stashes, and fast-forward sync."""
    try:
        report = run_doctor(repo=repo)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"repo_root={report.repo_root}")
    typer.echo(f"branch={report.branch}")
    typer.echo("status_porcelain=clean")
    typer.echo("stash_list=empty")
    typer.echo(f"worktree_base={(report.repo_root / '.worktrees').resolve()}")
    fetch_out = report.fetch.stdout.strip() or report.fetch.stderr.strip() or "(no output)"
    pull_out = report.pull.stdout.strip() or report.pull.stderr.strip() or "(no output)"
    typer.echo(f"fetch={fetch_out}")
    typer.echo(f"pull={pull_out}")


@app.command("start")
def start(
    tp_id: str = typer.Argument(..., metavar="TP_ID"),
    slug: str = typer.Argument(...),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        help="Repository path (defaults to current working directory).",
    ),
    reuse: bool = typer.Option(
        False,
        "--reuse",
        help="Reuse existing TP worktree only when branch and clean state match.",
    ),
) -> None:
    """Create deterministic TP branch + worktree from clean main."""
    try:
        result = start_tp(tp_id=tp_id, slug=slug, repo=repo, reuse=reuse)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"repo_root={result.doctor.repo_root}")
    typer.echo(f"tp_id={tp_id}")
    typer.echo(f"branch={result.branch}")
    typer.echo(f"worktree_path={result.worktree_path}")
    typer.echo(f"reused={str(result.reused).lower()}")
    typer.echo(f"next=cd {result.worktree_path}")


@app.command("status")
def status(
    tp_id: str = typer.Argument(..., metavar="TP_ID"),
) -> None:
    """Show TP workflow status (implemented in later commit)."""
    _ = tp_id
    typer.echo("taskx tp git status: TODO")


@app.command("pr")
def pr(
    tp_id: str = typer.Argument(..., metavar="TP_ID"),
) -> None:
    """Create PR for TP branch (implemented in later commit)."""
    _ = tp_id
    typer.echo("taskx tp git pr: TODO")


@app.command("merge")
def merge(
    tp_id: str = typer.Argument(..., metavar="TP_ID"),
) -> None:
    """Merge TP PR (implemented in later commit)."""
    _ = tp_id
    typer.echo("taskx tp git merge: TODO")


@app.command("sync-main")
def sync_main() -> None:
    """Sync main branch (implemented in later commit)."""
    typer.echo("taskx tp git sync-main: TODO")


@app.command("cleanup")
def cleanup(
    tp_id: str = typer.Argument(..., metavar="TP_ID"),
) -> None:
    """Remove TP worktree (implemented in later commit)."""
    _ = tp_id
    typer.echo("taskx tp git cleanup: TODO")


@app.command("list")
def list_cmd() -> None:
    """List TP worktrees (implemented in later commit)."""
    typer.echo("taskx tp git list: TODO")
