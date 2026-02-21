"""CLI registration for taskx tp run commands."""

from __future__ import annotations

import typer


def register(tp_app: typer.Typer) -> None:
    """Attach tp run command to the tp group."""

    @tp_app.command("run")
    def tp_run(
        tp_id: str = typer.Argument(..., metavar="TP_ID"),
        slug: str = typer.Argument(...),
    ) -> None:
        """Run complete TP lifecycle (implemented in later commits)."""
        _ = (tp_id, slug)
        typer.echo("taskx tp run: TODO")
