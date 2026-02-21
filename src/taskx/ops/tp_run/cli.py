"""CLI registration for taskx tp run commands."""

from __future__ import annotations

from pathlib import Path

import typer

from taskx.ops.tp_git.guards import resolve_repo_root
from taskx.ops.tp_git.naming import normalize_slug
from taskx.ops.tp_run.plan import RunOptions, execute_run
from taskx.ops.tp_run.proof import ProofWriter, build_run_id, resolve_paths


def register(tp_app: typer.Typer) -> None:
    """Attach tp run command to the tp group."""

    @tp_app.command("run")
    def tp_run(
        tp_id: str = typer.Argument(..., metavar="TP_ID"),
        slug: str = typer.Argument(...),
        repo: Path | None = typer.Option(None, "--repo", help="Repository path."),
        dry_run: bool = typer.Option(False, "--dry-run", help="Generate proof pack without mutating git state."),
        continue_mode: bool = typer.Option(False, "--continue", help="Continue using existing TP worktree."),
        stop_after: str | None = typer.Option(
            None,
            "--stop-after",
            help="Stop after a stage: doctor|start|test|pr|merge|sync|cleanup.",
        ),
        test_cmd: str | None = typer.Option(
            None,
            "--test-cmd",
            help="Optional test command to run inside TP worktree (example: 'pytest -q').",
        ),
        pr_title: str | None = typer.Option(None, "--pr-title", help="Pull request title override."),
        pr_body: str | None = typer.Option(None, "--pr-body", help="Pull request body override."),
        pr_body_file: Path | None = typer.Option(None, "--pr-body-file", help="Pull request body file path."),
        wait_merge: bool = typer.Option(False, "--wait-merge", help="Wait for merged PR state."),
        wait_timeout_sec: int = typer.Option(900, "--wait-timeout-sec", help="Wait timeout in seconds."),
        merge_enabled: bool = typer.Option(True, "--merge/--no-merge", help="Attempt merge after PR creation."),
    ) -> None:
        """Run complete TP lifecycle (scaffold; writes deterministic proof pack)."""
        try:
            repo_root = resolve_repo_root(repo)
        except RuntimeError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc

        normalized_slug = normalize_slug(slug)
        run_id = build_run_id(tp_id=tp_id, repo_root=repo_root)
        paths = resolve_paths(repo_root=repo_root, tp_id=tp_id, run_id=run_id)
        writer = ProofWriter(paths)

        if dry_run:
            writer.write_json(
                "RUN.json",
                {
                    "tp_id": tp_id,
                    "slug": normalized_slug,
                    "run_id": run_id,
                    "repo_root": str(repo_root),
                    "proof_dir": str(paths.run_dir),
                    "dry_run": True,
                },
            )
            typer.echo(f"repo_root={repo_root}")
            typer.echo(f"tp_id={tp_id}")
            typer.echo(f"slug={normalized_slug}")
            typer.echo(f"run_id={run_id}")
            typer.echo(f"proof_dir={paths.run_dir}")
            typer.echo("mode=dry-run")
            raise typer.Exit(0)

        if stop_after not in {None, "doctor", "start", "test", "pr", "merge", "sync", "cleanup"}:
            typer.echo("invalid --stop-after value", err=True)
            raise typer.Exit(1)
        if pr_body is not None and pr_body_file is not None:
            typer.echo("pass either --pr-body or --pr-body-file, not both", err=True)
            raise typer.Exit(1)

        result = execute_run(
            RunOptions(
                repo_root=repo_root,
                tp_id=tp_id,
                slug=normalized_slug,
                run_id=run_id,
                continue_mode=continue_mode,
                stop_after=stop_after,  # type: ignore[arg-type]
                test_cmd=test_cmd,
                pr_title=pr_title,
                pr_body=pr_body,
                pr_body_file=pr_body_file,
                wait_merge=wait_merge,
                wait_timeout_sec=wait_timeout_sec,
                merge_enabled=merge_enabled,
            ),
            writer,
        )

        typer.echo(f"repo_root={repo_root}")
        typer.echo(f"tp_id={tp_id}")
        typer.echo(f"slug={normalized_slug}")
        typer.echo(f"run_id={run_id}")
        typer.echo(f"proof_dir={paths.run_dir}")
        if result.worktree_path is not None:
            typer.echo(f"worktree_path={result.worktree_path}")
        if result.branch is not None:
            typer.echo(f"branch={result.branch}")
        typer.echo(result.message.strip())
        if result.exit_code != 0:
            raise typer.Exit(result.exit_code)
