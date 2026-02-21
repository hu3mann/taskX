"""CLI surface for taskx tp git workflows."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="git",
    help="Task Packet git workflow commands",
    no_args_is_help=True,
)


@app.command("doctor")
def doctor() -> None:
    """Fail-closed repo gate (implemented in later commit)."""
    typer.echo("taskx tp git doctor: TODO")


@app.command("start")
def start(
    tp_id: str = typer.Argument(..., metavar="TP_ID"),
    slug: str = typer.Argument(...),
) -> None:
    """Create deterministic TP branch + worktree (implemented in later commit)."""
    _ = (tp_id, slug)
    typer.echo("taskx tp git start: TODO")


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
