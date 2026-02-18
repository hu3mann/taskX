"""TaskX Ultra-Min CLI - Task Packet Lifecycle Commands Only."""

import json
import os
import re
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Any

import click
import typer
from rich.console import Console

from taskx import __version__
from taskx.manifest import (
    append_command_record,
    check_manifest,
    finalize_manifest,
    init_manifest,
    load_manifest,
    manifest_exists,
    save_manifest,
)
from taskx.manifest import (
    get_timestamp as get_manifest_timestamp,
)
from taskx.obs.run_artifacts import (
    COMMIT_RUN_FILENAME,
    PROMOTION_LEGACY_FILENAME,
    PROMOTION_TOKEN_FILENAME,
    VIOLATIONS_FILENAME,
    get_default_run_root,
    make_run_id,
    normalize_timestamp_mode,
    resolve_run_dir,
    to_pipeline_timestamp_mode,
)
from taskx.orchestrator import orchestrate as orchestrate_packet
from taskx.pr import PrOpenRefusal, run_pr_open
from taskx.router import (
    build_route_plan,
    ensure_default_availability,
    render_handoff_markdown,
    render_route_plan_markdown,
    route_plan_from_dict,
    route_plan_to_dict,
)
from taskx.router import (
    explain_step as explain_route_step,
)
from taskx.router import (
    parse_steps as parse_route_steps,
)
from taskx.router.types import DEFAULT_PLAN_RELATIVE_PATH
from taskx.ui import (
    THEMES,
    NeonSpinner,
    console as neon_console,
    get_theme_name,
    neon_enabled,
    render_banner,
    should_show_banner,
    sleep_ms,
    strict_enabled,
    worship as worship_impl,
)

# Import pipeline modules (from migrated taskx code)
try:
    from taskx.pipeline.task_compiler.compiler import compile_task_queue
except ImportError:
    compile_task_queue = None  # type: ignore

try:
    from taskx.pipeline.task_runner.runner import create_run_workspace
except ImportError:
    create_run_workspace = None  # type: ignore

try:
    from taskx.pipeline.evidence.collector import collect_evidence as collect_evidence_impl
except ImportError:
    collect_evidence_impl = None  # type: ignore

try:
    from taskx.pipeline.compliance.gate import run_allowlist_gate
except ImportError:
    run_allowlist_gate = None  # type: ignore

try:
    from taskx.pipeline.promotion.gate import promote_run as promote_run_impl
except ImportError:
    promote_run_impl = None  # type: ignore

try:
    from taskx.pipeline.spec_feedback.feedback import generate_feedback as generate_spec_feedback
except ImportError:
    generate_spec_feedback = None  # type: ignore

try:
    from taskx.pipeline.loop.orchestrator import run_loop
    from taskx.pipeline.loop.types import LoopInputs
    LOOP_AVAILABLE = True
except ImportError:
    run_loop = None  # type: ignore
    LOOP_AVAILABLE = False

try:
    from taskx.pipeline.bundle.exporter import BundleExporter
except ImportError:
    BundleExporter = None  # type: ignore

try:
    from taskx.pipeline.bundle.ingester import ingest_bundle as ingest_bundle_impl
except ImportError:
    ingest_bundle_impl = None  # type: ignore

try:
    from taskx.pipeline.case.auditor import audit_case as audit_case_impl
except ImportError:
    audit_case_impl = None  # type: ignore

try:
    from taskx.ops.cli import app as ops_app
except ImportError:
    ops_app = None  # type: ignore


cli = typer.Typer(
    name="taskx",
    help="TaskX - Minimal Task Packet Lifecycle CLI",
    no_args_is_help=True,
    add_help_option=False,
)
if ops_app:
    cli.add_typer(ops_app, name="ops")
console = Console()

neon_app = typer.Typer(help="Neon terminal cosmetics (console-only). Artifacts stay sterile.")
cli.add_typer(neon_app, name="neon")


def _use_compat_options(*_values: object) -> None:
    """Mark backward-compatible CLI options as intentionally accepted."""


class DirtyPolicy(str, Enum):
    """Dirty working tree handling policy for deterministic commands."""

    REFUSE = "refuse"
    STASH = "stash"


class FinishMode(str, Enum):
    """Supported finish strategies."""

    REBASE_FF = "rebase-ff"


def _version_option_callback(value: bool) -> None:
    """Handle eager --version option."""
    if value:
        if should_show_banner(sys.argv):
            render_banner()
        typer.echo(__version__)
        raise typer.Exit()


def _help_option_callback(value: bool) -> None:
    """Handle eager --help option (so we can show banner on help)."""
    if value:
        if should_show_banner(sys.argv):
            render_banner()
        ctx = click.get_current_context()
        typer.echo(ctx.get_help())
        raise typer.Exit()


@cli.callback(invoke_without_command=True)
def _cli_callback(
    ctx: typer.Context,
    help: bool = typer.Option(
        False,
        "--help",
        "-h",
        help="Show this message and exit.",
        is_eager=True,
        callback=_help_option_callback,
    ),
    version: bool = typer.Option(
        False,
        "--version",
        help="Show TaskX version and exit.",
        is_eager=True,
        callback=_version_option_callback,
    ),
) -> None:
    """
    CLI callback that runs on every invocation.

    Checks for import shadowing issues and emits warnings.
    """
    _ = version
    _use_compat_options(help)
    if should_show_banner(sys.argv):
        render_banner()
    # Skip shadowing check for print-runtime-origin command
    if ctx.invoked_subcommand != "print-runtime-origin":
        _check_import_shadowing()


def _check_import_shadowing() -> None:
    """
    Check if taskx is being imported from an unexpected location.

    Emits a warning to stderr if taskx.__file__ is not in site-packages
    or the expected TaskX repository location.
    """
    import taskx

    taskx_file = taskx.__file__ or ""

    # Expected locations:
    # 1. site-packages/taskx/ (installed package)
    # 2. /code/taskX/ (editable install from TaskX repo)
    is_site_packages = "/site-packages/taskx/" in taskx_file
    is_taskx_repo = "/code/taskX/" in taskx_file

    if not is_site_packages and not is_taskx_repo:
        typer.echo(
            f"[bold yellow]WARNING: taskx is being imported from an unexpected location:[/bold yellow]\n"
            f"[yellow]  {taskx_file}[/yellow]\n"
            f"[yellow]This often indicates .pth shadowing or PYTHONPATH issues.[/yellow]\n"
            f"[yellow]Expected locations: */site-packages/taskx/ or */code/taskX/[/yellow]",
            err=True,
        )


@cli.command()
def worship() -> None:
    """Console-only easter egg (no artifacts)."""
    worship_impl()


@neon_app.callback(invoke_without_command=True)
def neon() -> None:
    """Show current neon theme banner."""
    render_banner()


@neon_app.command("list")
def neon_list() -> None:
    """List available neon themes."""
    for name in sorted(THEMES):
        if neon_enabled():
            neon_console.print(f"[bold]  {name}[/bold]")
        else:
            print(f"  {name}")


@neon_app.command("preview")
def neon_preview(
    theme: str = typer.Argument(..., help="Theme name."),
) -> None:
    """Preview a theme banner."""
    if theme not in THEMES:
        if neon_enabled():
            neon_console.print(f"[bold red]Unknown theme:[/bold red] {theme}")
            neon_console.print("Try: taskx neon list")
        else:
            print(f"Unknown theme: {theme}")
            print("Try: taskx neon list")
        raise typer.Exit(2)
    render_banner(theme=theme)


@neon_app.command("demo")
def neon_demo(
    delay_ms: int = typer.Option(220, "--delay-ms", help="Delay between themes (ms)."),
) -> None:
    """Cycle through all themes."""
    for theme in sorted(THEMES):
        render_banner(theme=theme)
        sleep_ms(delay_ms)


@neon_app.command("set")
def neon_set(
    theme: str = typer.Argument(..., help="Theme name."),
) -> None:
    """Print a shell export line for TASKX_THEME."""
    if theme not in THEMES:
        if neon_enabled():
            neon_console.print(f"[bold red]Unknown theme:[/bold red] {theme}")
            neon_console.print("Try: taskx neon list")
        else:
            print(f"Unknown theme: {theme}")
            print("Try: taskx neon list")
        raise typer.Exit(2)
    line = f'export TASKX_THEME="{theme}"'
    if neon_enabled():
        neon_console.print("[bold bright_green]Copy/paste into your shell:[/bold bright_green]")
        neon_console.print(line)
    else:
        print(line)


@neon_app.command("status")
def neon_status() -> None:
    """Show neon/strict toggles and selected theme."""
    enabled = "1" if neon_enabled() else "0"
    strict = "1" if strict_enabled() else "0"
    theme = get_theme_name()
    lines = [
        f"TASKX_NEON={enabled}",
        f"TASKX_THEME={theme}",
        f"TASKX_STRICT={strict}",
    ]
    if neon_enabled():
        neon_console.print("[bold]Neon status[/bold]")
        for s in lines:
            neon_console.print(f"  {s}")
    else:
        for s in lines:
            print(s)


@neon_app.command("persist")
def neon_persist(
    shell: str = typer.Option(
        "auto",
        "--shell",
        help="Target shell rc format: zsh, bash, or auto (infer from $SHELL).",
    ),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Override rc file path (otherwise derived from --shell).",
    ),
    remove: bool = typer.Option(
        False,
        "--remove",
        help="Remove the managed TASKX NEON block.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run",
        help="Print a unified diff and do not write.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Write changes to disk (creates timestamped backup).",
    ),
    theme: str | None = typer.Option(
        None,
        "--theme",
        help="Theme override (default: TASKX_THEME or mintwave).",
    ),
    neon: int | None = typer.Option(
        None,
        "--neon",
        help="Override TASKX_NEON (0 or 1).",
    ),
    strict: int | None = typer.Option(
        None,
        "--strict",
        help="Override TASKX_STRICT (0 or 1).",
    ),
) -> None:
    """Persist neon env exports into a shell rc file (idempotent markers)."""
    if yes and dry_run:
        if neon_enabled():
            neon_console.print(
                "[bold red]Refused:[/bold red] --yes and --dry-run are mutually exclusive. "
                "Use either --yes to write changes or --dry-run to preview them."
            )
        else:
            print(
                "Refused: --yes and --dry-run are mutually exclusive. "
                "Use either --yes to write changes or --dry-run to preview them."
            )
        raise typer.Exit(2)

    if path is None:
        resolved_shell = shell
        if resolved_shell == "auto":
            shell_env = os.environ.get("SHELL", "")
            if shell_env.endswith("zsh"):
                resolved_shell = "zsh"
            elif shell_env.endswith("bash"):
                resolved_shell = "bash"
            else:
                if neon_enabled():
                    neon_console.print("[bold red]Refused:[/bold red] unable to infer shell from $SHELL.")
                    neon_console.print("Provide --shell zsh|bash or --path /path/to/rcfile")
                else:
                    print("Refused: unable to infer shell from $SHELL. Provide --shell zsh|bash or --path.")
                raise typer.Exit(2)

        if resolved_shell == "zsh":
            path = Path.home() / ".zshrc"
        elif resolved_shell == "bash":
            path = Path.home() / ".bashrc"
        else:
            if neon_enabled():
                neon_console.print(
                    f"[bold red]Refused:[/bold red] unsupported shell '{resolved_shell}'."
                )
                neon_console.print("Provide --shell zsh|bash or --path /path/to/rcfile")
            else:
                print(
                    f"Refused: unsupported shell '{resolved_shell}'. "
                    "Provide --shell zsh|bash or --path /path/to/rcfile."
                )
            raise typer.Exit(2)

    desired_neon = str(neon) if neon is not None else os.getenv("TASKX_NEON", "1")
    desired_strict = str(strict) if strict is not None else os.getenv("TASKX_STRICT", "0")
    desired_theme = theme or os.getenv("TASKX_THEME", "mintwave")

    # Validate theme against known themes to prevent shell injection
    if desired_theme not in THEMES:
        if neon_enabled():
            neon_console.print(f"[bold red]Unknown theme:[/bold red] {desired_theme}")
            neon_console.print("Try: taskx neon list")
        else:
            print(f"Unknown theme: {desired_theme}")
            print("Try: taskx neon list")
        raise typer.Exit(2)

    if desired_neon not in ("0", "1") or desired_strict not in ("0", "1"):
        if neon_enabled():
            if desired_neon not in ("0", "1"):
                neon_console.print(
                    f"[bold red]Refused:[/bold red] invalid TASKX_NEON value {desired_neon!r}. "
                    "Expected '0' or '1'."
                )
            if desired_strict not in ("0", "1"):
                neon_console.print(
                    f"[bold red]Refused:[/bold red] invalid TASKX_STRICT value {desired_strict!r}. "
                    "Expected '0' or '1'."
                )
        else:
            if desired_neon not in ("0", "1"):
                print(
                    f"Refused: invalid TASKX_NEON value {desired_neon!r}. Expected '0' or '1'."
                )
            if desired_strict not in ("0", "1"):
                print(
                    f"Refused: invalid TASKX_STRICT value {desired_strict!r}. Expected '0' or '1'."
                )
        raise typer.Exit(2)

    from taskx.neon_persist import persist_rc_file

    try:
        result = persist_rc_file(
            path=path,
            neon=desired_neon,
            theme=desired_theme,
            strict=desired_strict,
            remove=remove,
            dry_run=not yes,
        )
    except ValueError as exc:
        # Malformed markers in the rc file; present a friendly error instead of a traceback.
        if neon_enabled():
            neon_console.print(
                f"[bold red]Error:[/bold red] Failed to update rc file {path} due to malformed markers."
            )
            neon_console.print(f"[dim]{exc}[/dim]")
        else:
            print(f"Error: Failed to update rc file {path} due to malformed markers.")
            print(exc)
        raise typer.Exit(1)

    if neon_enabled():
        neon_console.print(f"[bold]Target:[/bold] {result.path}")
        neon_console.print("[dim]Mode: dry-run[/dim]" if not yes else "[dim]Mode: write[/dim]")
    else:
        print(f"Target: {result.path}")
        print("Mode: dry-run" if not yes else "Mode: write")

    if result.diff:
        print(result.diff, end="" if result.diff.endswith("\n") else "\n")
    else:
        if neon_enabled():
            neon_console.print("[green]No changes.[/green]")
        else:
            print("No changes.")

    if result.backup_path is not None:
        if neon_enabled():
            neon_console.print(f"[cyan]Backup:[/cyan] {result.backup_path}")
        else:
            print(f"Backup: {result.backup_path}")


def _check_repo_guard(bypass: bool, rescue_patch: str | None = None) -> Path:
    """
    Check TaskX repo guard unless bypassed.

    Args:
        bypass: If True, skip guard check and warn user

    Returns:
        Path to detected repo root (or cwd if bypassed)

    Raises:
        RuntimeError: If guard check fails and not bypassed
    """
    from taskx.safety.wip_rescue import write_rescue_patch
    from taskx.utils.repo import detect_repo_root, require_taskx_repo_root

    cwd = Path.cwd()

    if bypass:
        console.print(
            "[bold yellow]⚠️  WARNING: Repo guard bypassed![/bold yellow]\n"
            "[yellow]Running stateful command without TaskX repo detection.[/yellow]"
        )
        return cwd

    try:
        # Stateful commands require explicit .taskxroot marker.
        return require_taskx_repo_root(
            cwd,
            allow_pyproject_fallback=False,
            stateful_command=True,
        )
    except RuntimeError as exc:
        if rescue_patch is None:
            raise

        try:
            detected_repo_root = detect_repo_root(cwd).root
        except RuntimeError:
            detected_repo_root = cwd

        patch_path = write_rescue_patch(
            repo_root=detected_repo_root,
            cwd=cwd,
            rescue_patch=rescue_patch,
        )
        raise RuntimeError(f"{exc}\nRescue patch written to: {patch_path}") from exc


def _require_module(module_func: Any, module_name: str) -> None:
    """Check if a required module is available."""
    if module_func is None:
        console.print(f"[bold red]Error:[/bold red] {module_name} module not available in this TaskX build")
        raise typer.Exit(1)


def _resolve_stateful_run_dir(
    run: Path | None,
    run_root: Path | None,
    timestamp_mode: str,
) -> Path:
    """Resolve target run directory for stateful commands."""
    selected_run = resolve_run_dir(
        run=run,
        run_root=run_root,
        timestamp_mode=timestamp_mode,
    )
    selected_run.parent.mkdir(parents=True, exist_ok=True)
    return selected_run


def _git_output(repo_root: Path, *args: str) -> str | None:
    """Best-effort git output helper."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), *args],
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None
    text = out.decode("utf-8", errors="replace").strip()
    return text or None


def _try_git_repo_root(cwd: Path) -> Path | None:
    """Resolve git root for current invocation, if available."""
    root = _git_output(cwd, "rev-parse", "--show-toplevel")
    if root is None:
        return None
    return Path(root).resolve()


def _load_repo_identity_for_command(cwd: Path) -> tuple[Path | None, Any | None]:
    """Load repo identity when configured for this repository."""
    from taskx.guard.identity import load_repo_identity

    repo_root = _try_git_repo_root(cwd)
    if repo_root is None:
        return None, None

    try:
        repo_identity = load_repo_identity(repo_root)
    except RuntimeError as exc:
        if str(exc).startswith("Repo identity file not found:"):
            return repo_root, None
        raise

    return repo_root, repo_identity


def _load_packet_identity_for_run(run_dir: Path, repo_identity: Any) -> Any | None:
    """Load packet identity declaration from run packet when available."""
    from taskx.pipeline.task_runner.parser import parse_packet_project_identity

    packet_path = run_dir / "TASK_PACKET.md"
    if not packet_path.exists():
        return None
    try:
        return parse_packet_project_identity(
            packet_path,
            packet_required_header=bool(repo_identity.packet_required_header),
        )
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc


def _sanitize_branch_token(value: str) -> str:
    """Normalize text into deterministic branch-token format."""
    token = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return token or "run"


def _packet_id_from_run_packet(run_dir: Path) -> str | None:
    """Extract packet identifier from run TASK_PACKET.md first H1."""
    packet_path = run_dir / "TASK_PACKET.md"
    if not packet_path.exists():
        return None

    try:
        first_line = packet_path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return None

    match = re.match(r"^#\s+TASK_PACKET\s+(TP_\d{4})\b", first_line)
    if match is None:
        return None
    return match.group(1)


def _default_identity_branch(run_dir: Path, project_id: str) -> str:
    """Build canonical project-bound branch name for worktree start."""
    packet_id = _packet_id_from_run_packet(run_dir)
    run_slug = _sanitize_branch_token(run_dir.name)
    if packet_id is None:
        return f"tp/{project_id}/{run_slug}"
    packet_slug = _sanitize_branch_token(packet_id)
    return f"tp/{project_id}/{packet_slug}-{run_slug}"


def _enforce_run_identity_guards(
    *,
    run_dir: Path,
    require_branch: bool,
    quiet: bool,
) -> tuple[Path | None, Any | None]:
    """Apply packet/run/branch identity checks when repo identity is configured."""
    from taskx.guard.banner import (
        get_banner_context,
        print_identity_banner,
    )
    from taskx.guard.identity import (
        assert_repo_branch_identity,
        assert_repo_packet_identity,
        ensure_run_identity,
        origin_hint_warning,
        run_identity_origin_warning,
    )

    repo_root, repo_identity = _load_repo_identity_for_command(Path.cwd())
    if repo_root is None or repo_identity is None:
        return repo_root, repo_identity

    run_dir_resolved = run_dir.expanduser().resolve()
    packet_identity = _load_packet_identity_for_run(run_dir_resolved, repo_identity)
    assert_repo_packet_identity(repo_identity, packet_identity)

    run_identity = ensure_run_identity(run_dir_resolved, repo_identity, repo_root)
    run_warning = run_identity_origin_warning(repo_identity, run_identity)

    if require_branch:
        branch_name = _git_output(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
        if branch_name is not None:
            assert_repo_branch_identity(repo_identity, branch_name)

    banner_context = get_banner_context(
        repo_root,
        repo_identity.project_id,
        repo_identity.project_slug,
        repo_identity.repo_remote_hint,
        run_dir_resolved,
    )
    banner_warning = origin_hint_warning(
        repo_identity.repo_remote_hint,
        banner_context.origin_url,
    )
    print_identity_banner(banner_context, quiet=quiet)

    if not quiet and run_warning is not None and run_warning != banner_warning:
        typer.echo(run_warning, err=True)

    return repo_root, repo_identity


def _print_identity_banner_without_run(*, quiet: bool) -> None:
    """Print identity banner for commands that are not run-bound."""
    from taskx.guard.banner import (
        get_banner_context,
        print_identity_banner,
    )
    from taskx.guard.identity import assert_repo_branch_identity

    repo_root, repo_identity = _load_repo_identity_for_command(Path.cwd())
    if repo_root is None or repo_identity is None:
        return

    branch_name = _git_output(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch_name is not None:
        assert_repo_branch_identity(repo_identity, branch_name)

    banner_context = get_banner_context(
        repo_root,
        repo_identity.project_id,
        repo_identity.project_slug,
        repo_identity.repo_remote_hint,
        None,
    )
    print_identity_banner(banner_context, quiet=quiet)


def _sync_promotion_token_alias(run_dir: Path) -> None:
    """Write canonical PROMOTION_TOKEN.json alongside legacy PROMOTION.json."""
    legacy_path = run_dir / PROMOTION_LEGACY_FILENAME
    if not legacy_path.exists():
        return
    canonical_path = run_dir / PROMOTION_TOKEN_FILENAME
    shutil.copy2(legacy_path, canonical_path)


def _current_invocation_command() -> list[str]:
    """Return current CLI invocation in canonical taskx form."""
    if len(sys.argv) <= 1:
        return ["taskx"]
    return ["taskx", *sys.argv[1:]]


def _infer_task_packet_id(run_dir: Path) -> str:
    """Infer task packet id from RUN_ENVELOPE.json when available."""
    envelope_path = run_dir / "RUN_ENVELOPE.json"
    if envelope_path.exists():
        try:
            payload = json.loads(envelope_path.read_text(encoding="utf-8"))
            task_packet = payload.get("task_packet", {})
            if isinstance(task_packet, dict):
                task_id = task_packet.get("id")
                if isinstance(task_id, str) and task_id.strip():
                    return task_id
        except (json.JSONDecodeError, OSError):
            pass
    return "UNKNOWN"


def _artifact_ref_for_run(run_dir: Path, artifact_path: Path) -> str:
    """Convert artifact paths to run-relative when possible."""
    resolved_run_dir = run_dir.resolve()
    resolved_artifact = artifact_path.expanduser().resolve()
    try:
        return resolved_artifact.relative_to(resolved_run_dir).as_posix()
    except ValueError:
        return str(resolved_artifact)


def _ensure_manifest_ready(
    run_dir: Path,
    *,
    create_if_missing: bool,
    mode: str,
    timestamp_mode: str,
) -> bool:
    """Ensure run manifest exists if already present or explicitly requested."""
    resolved_run = run_dir.resolve()
    if manifest_exists(resolved_run):
        return True

    if not create_if_missing:
        return False

    if not resolved_run.exists():
        return False

    canonical_mode = normalize_timestamp_mode(timestamp_mode)
    init_manifest(
        run_dir=resolved_run,
        task_packet_id=_infer_task_packet_id(resolved_run),
        mode=mode,
        timestamp_mode=canonical_mode,
    )
    return True


def _append_manifest_command(
    *,
    enabled: bool,
    run_dir: Path | None,
    timestamp_mode: str,
    exit_code: int,
    started_at: str,
    stdout_lines: list[str],
    stderr_lines: list[str],
    expected_artifacts: list[str] | None = None,
    notes: str | None = None,
) -> None:
    """Write command record into TASK_PACKET_MANIFEST.json when enabled."""
    if not enabled or run_dir is None:
        return

    canonical_mode = normalize_timestamp_mode(timestamp_mode)
    try:
        append_command_record(
            run_dir=run_dir,
            cmd=_current_invocation_command(),
            cwd=Path.cwd(),
            exit_code=exit_code,
            stdout_text="\n".join(stdout_lines).strip(),
            stderr_text="\n".join(stderr_lines).strip(),
            timestamp_mode=canonical_mode,
            expected_artifacts=expected_artifacts or [],
            notes=notes,
            started_at=started_at,
            ended_at=get_manifest_timestamp(canonical_mode),
        )
    except Exception as exc:
        console.print(f"[yellow]Warning:[/yellow] Failed to update task packet manifest: {exc}")


manifest_app = typer.Typer(
    name="manifest",
    help="Task packet manifest lifecycle and replay checks",
    no_args_is_help=True,
)
cli.add_typer(manifest_app, name="manifest")


@manifest_app.command(name="init")
def manifest_init_cmd(
    run: Path = typer.Option(
        ...,
        "--run",
        help="Run directory for TASK_PACKET_MANIFEST.json",
    ),
    task_packet: str = typer.Option(
        ...,
        "--task-packet",
        help="Task packet identifier",
    ),
    mode: str = typer.Option(
        "ACT",
        "--mode",
        help="Execution mode (ACT, PLAN, etc.)",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        "--timestamp-mode",
        help="Timestamp mode: deterministic, now, or wallclock",
    ),
) -> None:
    """Initialize TASK_PACKET_MANIFEST.json in a run directory."""
    canonical_mode = normalize_timestamp_mode(timestamp_mode)
    created = init_manifest(
        run_dir=run.resolve(),
        task_packet_id=task_packet,
        mode=mode,
        timestamp_mode=canonical_mode,
    )
    console.print("[green]✓ Manifest initialized[/green]")
    console.print(f"[cyan]Run:[/cyan] {created['run_dir']}")
    console.print(f"[cyan]Path:[/cyan] {run.resolve() / 'TASK_PACKET_MANIFEST.json'}")


@manifest_app.command(name="finalize")
def manifest_finalize_cmd(
    run: Path = typer.Option(
        ...,
        "--run",
        help="Run directory containing TASK_PACKET_MANIFEST.json",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        help="Override status: passed or failed",
    ),
    artifact_expected: list[str] = typer.Option(
        [],
        "--artifact-expected",
        help="Expected artifact path (repeat option)",
    ),
    artifact_found: list[str] = typer.Option(
        [],
        "--artifact-found",
        help="Found artifact path (repeat option)",
    ),
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Optional manifest notes",
    ),
) -> None:
    """Finalize manifest artifact lists and run status."""
    manifest = load_manifest(run.resolve())
    if manifest is None:
        console.print(f"[bold red]Error:[/bold red] Manifest not found at {run.resolve() / 'TASK_PACKET_MANIFEST.json'}")
        raise typer.Exit(1)

    replay = check_manifest(run.resolve())
    expected = artifact_expected or replay["expected"]
    found = artifact_found or replay["found"]

    if status is None:
        status_value = "passed" if not replay["missing"] and not replay["extras"] else "failed"
    else:
        if status not in {"passed", "failed"}:
            console.print("[bold red]Error:[/bold red] --status must be 'passed' or 'failed'")
            raise typer.Exit(1)
        status_value = status

    existing_notes = manifest.get("notes")
    effective_notes = notes if notes is not None else (existing_notes if isinstance(existing_notes, str) else None)

    finalize_manifest(
        manifest=manifest,
        artifacts_expected=expected,
        artifacts_found=found,
        status=status_value,
        notes=effective_notes,
    )
    save_manifest(manifest, run.resolve())
    console.print(f"[green]✓ Manifest finalized ({status_value})[/green]")


@manifest_app.command(name="check")
def manifest_check_cmd(
    run: Path = typer.Option(
        ...,
        "--run",
        help="Run directory containing TASK_PACKET_MANIFEST.json",
    ),
) -> None:
    """Check expected artifacts from manifest against filesystem state."""
    try:
        replay = check_manifest(run.resolve())
    except FileNotFoundError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    manifest = load_manifest(run.resolve())
    if manifest is not None:
        existing_notes = manifest.get("notes")
        finalize_manifest(
            manifest=manifest,
            artifacts_expected=replay["expected"],
            artifacts_found=replay["found"],
            status="passed" if not replay["missing"] and not replay["extras"] else "failed",
            notes=existing_notes if isinstance(existing_notes, str) else None,
        )
        save_manifest(manifest, run.resolve())

    console.print(f"[cyan]Expected artifacts:[/cyan] {len(replay['expected'])}")
    console.print(f"[cyan]Found artifacts:[/cyan] {len(replay['found'])}")

    if replay["missing"]:
        console.print("[red]Missing artifacts:[/red]")
        for item in replay["missing"]:
            console.print(f"[red]  - {item}[/red]")
    if replay["extras"]:
        console.print("[yellow]Extra artifacts:[/yellow]")
        for item in replay["extras"]:
            console.print(f"[yellow]  - {item}[/yellow]")

    if replay["missing"] or replay["extras"]:
        raise typer.Exit(2)

    console.print("[green]✓ Manifest replay check passed[/green]")


@cli.command(name="print-runtime-origin", hidden=True)
def print_runtime_origin() -> None:
    """Print runtime import origin diagnostic information.

    Hidden diagnostic command to debug import shadowing issues.
    Shows where taskx is being imported from and sys.path ordering.
    """
    import sys

    import taskx

    console.print("[bold]TaskX Runtime Origin Diagnostic[/bold]\n")
    console.print(f"taskx.__file__: {taskx.__file__}")
    console.print(f"taskx.__version__: {__version__}")
    console.print(f"sys.executable: {sys.executable}")
    console.print("\nsys.path (first 10 entries):")
    for i, path in enumerate(sys.path[:10], 1):
        console.print(f"  {i}. {path}")

    raise typer.Exit(0)


class InitTier(str, Enum):
    """Bootstrap tier controlling what ``taskx init`` sets up."""

    OPS = "ops"
    STANDARD = "standard"
    DEEP = "deep"


@cli.command(name="init")
def init_cmd(
    tier: InitTier = typer.Option(
        InitTier.STANDARD,
        "--tier",
        help="Bootstrap tier: ops (operator prompts only), standard (ops + project files), deep (all + adapter wiring).",
    ),
    preset: str = typer.Option(
        "taskx",
        "--preset",
        help="Directive preset for project init (taskx, chatx, both, none).",
    ),
    platform: str = typer.Option(
        "chatgpt",
        "--platform",
        help="Target platform for operator prompt.",
    ),
    adapter: str | None = typer.Option(
        None,
        "--adapter",
        help="Adapter name to wire (discovered via taskx.adapters entry points).",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Non-interactive mode: accept all defaults, skip prompts.",
    ),
    out: Path = typer.Option(
        Path("."),
        "--out",
        help="Output directory for project files (standard/deep tiers).",
    ),
) -> None:
    """Bootstrap TaskX integration into the current repository.

    Tier controls scope:
    - ops: operator prompt configuration only (ops/ directory)
    - standard: ops + project directive files
    - deep: standard + adapter wiring via entry-point discovery
    """
    _use_compat_options(yes)  # consumed by CLI interface; suppresses interactive prompts

    from taskx.utils.repo import detect_repo_root

    # Determine repo root best-effort
    cwd = Path.cwd()
    try:
        repo_root_path = detect_repo_root(cwd).root
    except RuntimeError:
        repo_root_path = cwd

    # --- Tier: ops (and above) ---
    # Always run ops init
    if ops_app is not None:
        from taskx.ops.cli import run_export_flow as _ops_export

        # Prepare ops directory
        ops_dir = repo_root_path / "ops"
        ops_dir.mkdir(exist_ok=True)

        profile_path = ops_dir / "operator_profile.yaml"
        if not profile_path.exists():
            import yaml

            profile = {
                "project": {
                    "name": repo_root_path.name,
                    "repo_root": str(repo_root_path),
                    "timezone": "America/Vancouver",
                },
                "taskx": {
                    "pin_type": "git_commit",
                    "pin_value": "UNKNOWN",
                    "cli_min_version": __version__,
                },
                "platform": {
                    "target": platform,
                    "model": "gpt-5.2-thinking",
                },
            }
            with open(profile_path, "w") as f:
                yaml.dump(profile, f)
            console.print(f"[green]Created {profile_path}[/green]")

        templates_dir = ops_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        (templates_dir / "overlays").mkdir(exist_ok=True)

        overlay_p = templates_dir / "overlays" / f"{platform}.md"
        if not overlay_p.exists():
            overlay_p.write_text(f"# {platform} Overlay\nSpecifics for {platform}\n")

        try:
            _ops_export(platform=platform)
        except Exception:
            console.print("[yellow]Warning: ops export failed (templates may be missing).[/yellow]")

        console.print("[green]Ops tier: complete.[/green]")

    # --- Tier: standard (and above) ---
    if tier in (InitTier.STANDARD, InitTier.DEEP):
        from taskx.project.init import init_project

        try:
            result = init_project(out_dir=out.resolve(), preset=preset)
            created = sum(1 for f in result["files"] if f["status"] == "created")
            updated = sum(1 for f in result["files"] if f["status"] == "updated")
            console.print(f"[green]Project tier: {created} created, {updated} updated.[/green]")
        except Exception as exc:
            console.print(f"[yellow]Warning: project init failed: {exc}[/yellow]")

    # --- Tier: deep ---
    if tier == InitTier.DEEP:
        from taskx_adapters import discover_adapters, get_adapter

        if adapter:
            found = get_adapter(adapter)
            if found is None:
                console.print(f"[yellow]Adapter '{adapter}' not found in entry points.[/yellow]")
            else:
                console.print(f"[green]Adapter '{found.name}' available.[/green]")
        else:
            adapters = list(discover_adapters())
            if adapters:
                names = ", ".join(a.name for a in adapters)
                console.print(f"[green]Discovered adapters: {names}[/green]")
            else:
                console.print("[dim]No adapters discovered via entry points.[/dim]")

    console.print(f"[bold green]taskx init complete (tier={tier.value}).[/bold green]")


@cli.command()
def compile_tasks(
    mode: str = typer.Option(
        "mvp",
        help="Compilation mode: mvp, hardening, or full",
    ),
    max_packets: int | None = typer.Option(
        None,
        help="Maximum number of task packets to generate",
    ),
    out: Path = typer.Option(
        Path("./out/tasks"),
        help="Output directory for compiled task packets",
    ),
    repo_root: Path | None = typer.Option(
        None,
        help="Repository root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic, now, or wallclock",
    ),
) -> None:
    """Compile task packets from spec."""
    _require_module(compile_task_queue, "task_compiler")
    _use_compat_options(project_root)

    console.print("[cyan]Compiling task packets...[/cyan]")

    # Resolve paths (assumes spec_mine structure)
    effective_repo_root = repo_root or Path.cwd()
    spec_path = effective_repo_root / "spec_mine" / "MASTER_DESIGN_SPEC_V3.md"
    source_index_path = effective_repo_root / "spec_mine" / "SOURCE_INDEX.json"

    if not spec_path.exists():
        console.print(f"[bold red]Error:[/bold red] Spec not found at {spec_path}")
        raise typer.Exit(1)
    if not source_index_path.exists():
        console.print(f"[bold red]Error:[/bold red] Source index not found at {source_index_path}")
        raise typer.Exit(1)

    try:
        compile_task_queue(
            spec_path=spec_path,
            source_index_path=source_index_path,
            output_dir=out,
            mode=mode,
            max_packets=max_packets if max_packets else 100,
            seed=42,  # Fixed seed for CLI
            pipeline_version=__version__,
            timestamp_mode=timestamp_mode,
        )
        console.print("[green]✓ Task compilation complete[/green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@cli.command()
def run_task(
    task_id: str = typer.Option(
        ...,
        help="Task packet ID to execute",
    ),
    task_queue: Path = typer.Option(
        Path("./out/tasks/task_queue.json"),
        help="Path to task queue file",
    ),
    run_root: Path | None = typer.Option(
        None,
        "--run-root",
        help="Run root directory (default resolves via --run-root, TASKX_RUN_ROOT, repo root, then cwd)",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Deprecated alias for --run-root",
        hidden=True,
    ),
    repo_root: Path | None = typer.Option(
        None,
        help="Repository root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic, now, or wallclock",
    ),
) -> None:
    """Execute a task packet (create run workspace)."""
    _require_module(create_run_workspace, "task_runner")
    _use_compat_options(repo_root, project_root)

    canonical_mode = normalize_timestamp_mode(timestamp_mode)
    pipeline_timestamp_mode = to_pipeline_timestamp_mode(timestamp_mode)
    effective_run_root = get_default_run_root(cli_run_root=run_root or out)
    effective_run_root.mkdir(parents=True, exist_ok=True)
    run_id = make_run_id(prefix="RUN", timestamp_mode=canonical_mode)

    console.print(f"[cyan]Preparing run for task: {task_id}[/cyan]")
    console.print(f"[cyan]Run root:[/cyan] {effective_run_root}")
    console.print(f"[cyan]Run ID:[/cyan] {run_id}")

    # Find task packet
    # Assumes TASK_PACKETS is sibling of task_queue or in ./out/tasks/TASK_PACKETS
    task_packets_dir = task_queue.parent / "TASK_PACKETS"
    if not task_packets_dir.exists():
        # Fallback to standard location if queue path is weird
        task_packets_dir = Path("./out/tasks/TASK_PACKETS")

    if not task_packets_dir.exists():
         console.print(f"[bold red]Error:[/bold red] Could not locate TASK_PACKETS directory (checked {task_packets_dir})")
         raise typer.Exit(1)

    candidates = list(task_packets_dir.glob(f"{task_id}_*.md"))
    if not candidates:
        console.print(f"[bold red]Error:[/bold red] Task packet {task_id} not found in {task_packets_dir}")
        raise typer.Exit(1)

    packet_path = candidates[0].resolve()

    try:
        result = create_run_workspace(
            task_packet_path=packet_path,
            output_dir=effective_run_root,
            run_id=run_id,
            timestamp_mode=pipeline_timestamp_mode,
            pipeline_version=__version__,
        )
        console.print(f"[green]✓ Workpace created at: {result['run_dir']}[/green]")
        console.print("[cyan]To implement:[/cyan] Follow instructions in PLAN.md")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@cli.command()
def collect_evidence(
    run: Path = typer.Option(
        ...,
        help="Path to run directory",
    ),
    max_claims: int = typer.Option(
        100,
        help="Maximum number of claims to extract",
    ),
    max_evidence_chars: int = typer.Option(
        50000,
        help="Maximum characters of evidence to collect",
    ),
    repo_root: Path | None = typer.Option(
        None,
        help="Repository root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic, now, or wallclock",
    ),
) -> None:
    """Collect verification evidence from a task run."""
    _require_module(collect_evidence_impl, "evidence")
    _use_compat_options(repo_root, project_root)

    console.print("[cyan]Collecting evidence...[/cyan]")

    try:
        collect_evidence_impl(
            run_dir=run,
            max_claims=max_claims,
            max_evidence_chars=max_evidence_chars,
            timestamp_mode=timestamp_mode,
            pipeline_version=__version__,
        )
        console.print("[green]✓ Evidence collection complete[/green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@cli.command()
def gate_allowlist(
    run: Path | None = typer.Option(
        None,
        "--run",
        help="Path to run directory (default <run-root>/<run-id>)",
    ),
    run_root: Path | None = typer.Option(
        None,
        "--run-root",
        help="Run root used when --run is omitted",
    ),
    diff_mode: str = typer.Option(
        "auto",
        help="Diff detection mode: git, fs, or auto",
    ),
    require_verification_evidence: bool = typer.Option(
        True,
        help="Require verification evidence to pass gate",
    ),
    repo_root: Path | None = typer.Option(
        None,
        help="Repository root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic, now, or wallclock",
    ),
    no_repo_guard: bool = typer.Option(
        False,
        "--no-repo-guard",
        help="Skip TaskX repo detection (use with caution)",
    ),
    manifest: bool = typer.Option(
        False,
        "--manifest",
        help="Initialize manifest if missing and append this command record",
    ),
    rescue_patch: str | None = typer.Option(
        None,
        "--rescue-patch",
        help="Write a rescue patch on guard failure (path or 'auto')",
    ),
) -> None:
    """Run allowlist compliance gate on a task run."""
    _require_module(run_allowlist_gate, "compliance")
    _use_compat_options(project_root)

    selected_run: Path | None = None
    manifest_enabled = False
    manifest_started_at = get_manifest_timestamp("deterministic")
    manifest_stdout: list[str] = []
    manifest_stderr: list[str] = []
    manifest_exit_code = 1

    try:
        manifest_started_at = get_manifest_timestamp(normalize_timestamp_mode(timestamp_mode))
        guarded_repo_root = _check_repo_guard(no_repo_guard, rescue_patch=rescue_patch)

        # Resolve repo root
        selected_run = _resolve_stateful_run_dir(run, run_root, timestamp_mode).resolve()
        manifest_enabled = _ensure_manifest_ready(
            selected_run,
            create_if_missing=manifest,
            mode="ACT",
            timestamp_mode=timestamp_mode,
        )
        pipeline_timestamp_mode = to_pipeline_timestamp_mode(timestamp_mode)
        effective_repo_root = (repo_root or guarded_repo_root).resolve()
        console.print("[cyan]Running allowlist gate...[/cyan]")
        console.print(f"[cyan]Run directory:[/cyan] {selected_run}")

        result = run_allowlist_gate(
            run_dir=selected_run,
            repo_root=effective_repo_root,
            timestamp_mode=pipeline_timestamp_mode,
            require_verification_evidence=require_verification_evidence,
            diff_mode=diff_mode,
            out_dir=selected_run,
        )

        if not result.violations:
            console.print("[green]✓ Allowlist gate passed[/green]")
            manifest_stdout.append("Allowlist gate passed")
            raise typer.Exit(0)
        else:
            console.print(f"[red]✗ Allowlist gate failed ({len(result.violations)} violations)[/red]")
            manifest_stdout.append(f"Allowlist gate failed ({len(result.violations)} violations)")
            for v in result.violations:
                console.print(f"[red]  - {v.type}: {v.message}[/red]")
                manifest_stdout.append(f"{v.type}: {v.message}")
            raise typer.Exit(2)

    except typer.Exit as exc:
        manifest_exit_code = int(exc.exit_code)
        raise
    except Exception as e:
        manifest_stderr.append(str(e))
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e
    finally:
        _append_manifest_command(
            enabled=manifest_enabled,
            run_dir=selected_run,
            timestamp_mode=timestamp_mode,
            exit_code=manifest_exit_code,
            started_at=manifest_started_at,
            stdout_lines=manifest_stdout,
            stderr_lines=manifest_stderr,
            expected_artifacts=["ALLOWLIST_DIFF.json", VIOLATIONS_FILENAME],
        )


@cli.command()
def promote_run(
    run: Path | None = typer.Option(
        None,
        "--run",
        help="Path to run directory (default <run-root>/<run-id>)",
    ),
    run_root: Path | None = typer.Option(
        None,
        "--run-root",
        help="Run root used when --run is omitted",
    ),
    require_run_summary: bool = typer.Option(
        False,
        help="Require RUN_SUMMARY.json to exist",
    ),
    repo_root: Path | None = typer.Option(
        None,
        help="Repository root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic, now, or wallclock",
    ),
    no_repo_guard: bool = typer.Option(
        False,
        "--no-repo-guard",
        help="Skip TaskX repo detection (use with caution)",
    ),
    manifest: bool = typer.Option(
        False,
        "--manifest",
        help="Initialize manifest if missing and append this command record",
    ),
    rescue_patch: str | None = typer.Option(
        None,
        "--rescue-patch",
        help="Write a rescue patch on guard failure (path or 'auto')",
    ),
) -> None:
    """Promote a task run by issuing completion token."""
    _require_module(promote_run_impl, "promotion")
    _use_compat_options(repo_root, project_root)

    selected_run: Path | None = None
    manifest_enabled = False
    manifest_started_at = get_manifest_timestamp("deterministic")
    manifest_stdout: list[str] = []
    manifest_stderr: list[str] = []
    manifest_exit_code = 1

    try:
        manifest_started_at = get_manifest_timestamp(normalize_timestamp_mode(timestamp_mode))
        _check_repo_guard(no_repo_guard, rescue_patch=rescue_patch)
        selected_run = _resolve_stateful_run_dir(run, run_root, timestamp_mode).resolve()
        manifest_enabled = _ensure_manifest_ready(
            selected_run,
            create_if_missing=manifest,
            mode="ACT",
            timestamp_mode=timestamp_mode,
        )
        pipeline_timestamp_mode = to_pipeline_timestamp_mode(timestamp_mode)
        console.print("[cyan]Promoting run...[/cyan]")
        console.print(f"[cyan]Run directory:[/cyan] {selected_run}")

        result = promote_run_impl(
            run_dir=selected_run,
            require_run_summary=require_run_summary,
            timestamp_mode=pipeline_timestamp_mode,
            out_dir=selected_run,
        )
        _sync_promotion_token_alias(selected_run)

        if result.status == "passed":
            console.print("[green]✓ Run promoted successfully[/green]")
            manifest_stdout.append("Run promoted successfully")
            raise typer.Exit(0)
        else:
            console.print("[red]✗ Run promotion failed[/red]")
            manifest_stdout.append("Run promotion failed")
            raise typer.Exit(2)
    except typer.Exit as exc:
        manifest_exit_code = int(exc.exit_code)
        raise
    except Exception as e:
        manifest_stderr.append(str(e))
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e
    finally:
        _append_manifest_command(
            enabled=manifest_enabled,
            run_dir=selected_run,
            timestamp_mode=timestamp_mode,
            exit_code=manifest_exit_code,
            started_at=manifest_started_at,
            stdout_lines=manifest_stdout,
            stderr_lines=manifest_stderr,
            expected_artifacts=[
                PROMOTION_LEGACY_FILENAME,
                "PROMOTION.md",
                PROMOTION_TOKEN_FILENAME,
            ],
        )


@cli.command()
def commit_run(
    run: Path | None = typer.Option(
        None,
        "--run",
        help="Path to run directory (default <run-root>/<run-id>)",
    ),
    run_root: Path | None = typer.Option(
        None,
        "--run-root",
        help="Run root used when --run is omitted",
    ),
    message: str | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Custom commit message (auto-generated if not provided)",
    ),
    allow_unpromoted: bool = typer.Option(
        False,
        "--allow-unpromoted",
        help="Allow commit without promotion token",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic, now, or wallclock",
    ),
    no_repo_guard: bool = typer.Option(
        False,
        "--no-repo-guard",
        help="Skip TaskX repo detection (use with caution)",
    ),
    manifest: bool = typer.Option(
        False,
        "--manifest",
        help="Initialize manifest if missing and append this command record",
    ),
    rescue_patch: str | None = typer.Option(
        None,
        "--rescue-patch",
        help="Write a rescue patch on guard failure (path or 'auto')",
    ),
) -> None:
    """Create git commit for a task run (allowlist-enforced).

    Only stages and commits files that are:
    1. In the allowlist (from ALLOWLIST_DIFF.json)
    2. Actually modified (per git status)

    Refuses to commit if:
    - Allowlist violations exist
    - Run is not promoted (unless --allow-unpromoted is used)
    - Not in a git repository

    Recommended workflow:
    1. taskx gate-allowlist --run <RUN_DIR>
    2. taskx promote-run --run <RUN_DIR>
    3. taskx commit-run --run <RUN_DIR>
    """
    from taskx.git.commit_run import commit_run as commit_run_impl

    selected_run: Path | None = None
    manifest_enabled = False
    manifest_started_at = get_manifest_timestamp("deterministic")
    manifest_stdout: list[str] = []
    manifest_stderr: list[str] = []
    manifest_exit_code = 1

    try:
        manifest_started_at = get_manifest_timestamp(normalize_timestamp_mode(timestamp_mode))
        _check_repo_guard(no_repo_guard, rescue_patch=rescue_patch)
        selected_run = _resolve_stateful_run_dir(run, run_root, timestamp_mode).resolve()
        manifest_enabled = _ensure_manifest_ready(
            selected_run,
            create_if_missing=manifest,
            mode="ACT",
            timestamp_mode=timestamp_mode,
        )
        pipeline_timestamp_mode = to_pipeline_timestamp_mode(timestamp_mode)
        console.print("[cyan]Creating commit for run...[/cyan]")
        console.print(f"[cyan]Run directory:[/cyan] {selected_run}")

        report = commit_run_impl(
            run_dir=selected_run,
            message=message,
            allow_unpromoted=allow_unpromoted,
            timestamp_mode=pipeline_timestamp_mode,
        )

        if report["status"] == "passed":
            console.print("[green]✓ Commit created successfully[/green]")
            console.print(f"[green]  Branch: {report['git']['branch']}[/green]")
            console.print(f"[green]  Commit: {report['git']['head_after']}[/green]")
            console.print(f"[green]  Files staged: {len(report['allowlist']['staged_files'])}[/green]")
            console.print(f"[green]  Report: {selected_run / COMMIT_RUN_FILENAME}[/green]")
            manifest_stdout.extend(
                [
                    "Commit created successfully",
                    f"Branch: {report['git']['branch']}",
                    f"Commit: {report['git']['head_after']}",
                    f"Files staged: {len(report['allowlist']['staged_files'])}",
                ]
            )
            raise typer.Exit(0)
        else:
            console.print("[red]✗ Commit failed[/red]")
            manifest_stdout.append("Commit failed")
            for error in report.get("errors", []):
                console.print(f"[red]  • {error}[/red]")
                manifest_stderr.append(str(error))
            raise typer.Exit(2)

    except typer.Exit as exc:
        manifest_exit_code = int(exc.exit_code)
        raise
    except Exception as e:
        manifest_stderr.append(str(e))
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e
    finally:
        _append_manifest_command(
            enabled=manifest_enabled,
            run_dir=selected_run,
            timestamp_mode=timestamp_mode,
            exit_code=manifest_exit_code,
            started_at=manifest_started_at,
            stdout_lines=manifest_stdout,
            stderr_lines=manifest_stderr,
            expected_artifacts=[COMMIT_RUN_FILENAME],
        )


@cli.command()
def spec_feedback(
    runs: list[Path] = typer.Option(
        ...,
        help="Paths to run directories",
    ),
    task_queue: Path = typer.Option(
        Path("./out/tasks/task_queue.json"),
        help="Path to task queue file",
    ),
    out: Path = typer.Option(
        Path("./out/feedback"),
        help="Output directory for feedback",
    ),
    require_promotion: bool = typer.Option(
        True,
        help="Only include promoted runs in feedback",
    ),
    repo_root: Path | None = typer.Option(
        None,
        help="Repository root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic, now, or wallclock",
    ),
) -> None:
    """Generate spec feedback from completed runs."""
    _require_module(generate_spec_feedback, "spec_feedback")
    _use_compat_options(repo_root, project_root)

    console.print("[cyan]Generating spec feedback...[/cyan]")

    try:
        # Filter runs if required
        target_runs = runs
        if require_promotion:
            target_runs = [r for r in runs if (r / "PROMOTION.json").exists()]

        generate_spec_feedback(
            run_paths=target_runs,
            task_queue_path=task_queue,
            output_dir=out,
            timestamp_mode=timestamp_mode,
        )
        console.print("[green]✓ Spec feedback generated[/green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@cli.command()
def loop(
    loop_id: str | None = typer.Option(
        None,
        help="Loop identifier (auto-generated if not provided)",
    ),
    out: Path = typer.Option(
        Path("./out/loops"),
        help="Output directory for loop artifacts",
    ),
    mode: str = typer.Option(
        "mvp",
        help="Loop mode: mvp, hardening, or full",
    ),
    run_task: str | None = typer.Option(
        None,
        help="Specific task ID to run in loop",
    ),
    collect_evidence: bool = typer.Option(
        True,
        help="Collect evidence after task execution",
    ),
    feedback: bool = typer.Option(
        True,
        help="Generate feedback after runs",
    ),
    max_packets: int = typer.Option(
        5,
        help="Maximum task packets to process",
    ),
    seed: int = typer.Option(
        42,
        help="Random seed for ordering",
    ),
    repo_root: Path | None = typer.Option(
        None,
        help="Repository root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Run complete task packet lifecycle loop."""
    _use_compat_options(project_root)
    if not LOOP_AVAILABLE:
        console.print("[bold red]Error:[/bold red] loop module not installed in this TaskX build")
        raise typer.Exit(1)

    _require_module(run_loop, "loop")

    console.print("[cyan]Starting task packet loop...[/cyan]")

    # Check repo root
    if repo_root is None:
        try:
            from taskx.utils.repo import find_taskx_repo_root
            repo_root = find_taskx_repo_root(Path.cwd()) or Path.cwd()
        except ImportError:
            repo_root = Path.cwd()

    try:
        inputs = LoopInputs(
            root=repo_root,
            mode=mode,
            max_packets=max_packets,
            seed=seed,
            run_task=run_task,
            run_id=None,  # Loop will auto-generate if needed
            collect_evidence=collect_evidence,
            feedback=feedback,
        )

        run_loop(
            loop_id=loop_id if loop_id else "LOOP_AUTO",
            loop_dir=out,
            inputs=inputs,
            timestamp_mode=timestamp_mode,
        )
        console.print("[green]✓ Loop execution complete[/green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


# ============================================================================
# Worktree + Commit Sequencing Commands
# ============================================================================

wt_app = typer.Typer(
    name="wt",
    help="Worktree lifecycle commands for deterministic packet execution",
    no_args_is_help=True,
)
cli.add_typer(wt_app, name="wt")


@wt_app.command(name="start")
def wt_start(
    run: Path = typer.Option(
        ...,
        "--run",
        help="Run directory for this Task Packet execution",
    ),
    branch: str | None = typer.Option(
        None,
        "--branch",
        help="Task branch name (default inferred from run directory)",
    ),
    base: str = typer.Option(
        "main",
        "--base",
        help="Base branch to branch from",
    ),
    remote: str = typer.Option(
        "origin",
        "--remote",
        help="Remote used for base branch fetch",
    ),
    worktree_path: Path | None = typer.Option(
        None,
        "--worktree-path",
        help="Explicit worktree path (default under out/worktrees)",
    ),
    dirty_policy: DirtyPolicy = typer.Option(
        DirtyPolicy.REFUSE,
        "--dirty-policy",
        help="Dirty state policy: refuse or stash",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Suppress identity banner output",
    ),
) -> None:
    """Create an isolated worktree + task branch for a Task Packet run.
    All packet commits must occur inside this worktree.
    Refuses to operate on a dirty repository unless --dirty-policy stash is provided.
    """
    from taskx.git.worktree_ops import start_worktree

    try:
        _repo_root, repo_identity = _enforce_run_identity_guards(
            run_dir=run,
            require_branch=True,
            quiet=quiet,
        )
        selected_branch = branch
        if selected_branch is None and repo_identity is not None:
            selected_branch = _default_identity_branch(run.expanduser().resolve(), repo_identity.project_id)

        result = start_worktree(
            run_dir=run,
            branch=selected_branch,
            base=base,
            remote=remote,
            worktree_path=worktree_path,
            dirty_policy=dirty_policy.value,
            cwd=Path.cwd(),
        )
    except RuntimeError as exc:
        console.print(str(exc))
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    console.print("[green]✓ Worktree initialized[/green]")
    console.print(f"[cyan]Branch:[/cyan] {result['branch']}")
    console.print(f"[cyan]Worktree:[/cyan] {result['worktree_path']}")
    console.print(f"[cyan]Artifact:[/cyan] {Path(result['run_dir']) / 'WORKTREE.json'}")


@cli.command(name="commit-sequence")
def commit_sequence_cmd(
    run: Path = typer.Option(
        ...,
        "--run",
        help="Run directory containing TASK_PACKET.md and artifacts",
    ),
    allow_unpromoted: bool = typer.Option(
        False,
        "--allow-unpromoted",
        help="Allow commit sequence without promotion token",
    ),
    dirty_policy: DirtyPolicy = typer.Option(
        DirtyPolicy.REFUSE,
        "--dirty-policy",
        help="Dirty state policy: refuse or stash",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Suppress identity banner output",
    ),
) -> None:
    """Execute the COMMIT PLAN defined in the Task Packet.
    Creates one commit per step, staging only allowlisted changed files.
    Refuses to run on main branch.
    Refuses if index contains pre-staged changes.
    """
    from taskx.git.worktree_ops import commit_sequence

    try:
        _enforce_run_identity_guards(
            run_dir=run,
            require_branch=True,
            quiet=quiet,
        )
        report = commit_sequence(
            run_dir=run,
            allow_unpromoted=allow_unpromoted,
            dirty_policy=dirty_policy.value,
            cwd=Path.cwd(),
        )
    except RuntimeError as exc:
        console.print(str(exc))
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    console.print("[green]✓ Commit sequence complete[/green]")
    console.print(f"[cyan]Commits:[/cyan] {len(report.get('steps', []))}")
    console.print(f"[cyan]Artifact:[/cyan] {run.resolve() / 'COMMIT_SEQUENCE_RUN.json'}")


@cli.command(name="finish")
def finish_cmd(
    run: Path = typer.Option(
        ...,
        "--run",
        help="Run directory for this Task Packet execution",
    ),
    mode: FinishMode = typer.Option(
        FinishMode.REBASE_FF,
        "--mode",
        help="Finish mode (default: rebase-ff)",
    ),
    cleanup: bool = typer.Option(
        True,
        "--cleanup/--no-cleanup",
        help="Remove task worktree and branch after successful finish",
    ),
    dirty_policy: DirtyPolicy = typer.Option(
        DirtyPolicy.REFUSE,
        "--dirty-policy",
        help="Dirty state policy: refuse or stash",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Suppress identity banner output",
    ),
) -> None:
    """Finalize a Task Packet run.
    Rebases task branch onto origin/main, fast-forwards main,
    pushes to remote, verifies sync, and optionally cleans up.
    """
    from taskx.git.worktree_ops import finish_run

    try:
        _enforce_run_identity_guards(
            run_dir=run,
            require_branch=True,
            quiet=quiet,
        )
        report = finish_run(
            run_dir=run,
            mode=mode.value,
            cleanup=cleanup,
            dirty_policy=dirty_policy.value,
            cwd=Path.cwd(),
        )
    except RuntimeError as exc:
        console.print(str(exc))
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    console.print("[green]✓ Finish complete[/green]")
    console.print(f"[cyan]Branch:[/cyan] {report['branch']}")
    console.print(f"[cyan]main after merge:[/cyan] {report['main_after_merge']}")
    console.print(f"[cyan]remote after push:[/cyan] {report['remote_after_push']}")
    console.print(f"[cyan]Artifact:[/cyan] {run.resolve() / 'FINISH.json'}")


# ============================================================================
# Docs Commands
# ============================================================================

docs_app = typer.Typer(
    name="docs",
    help="Documentation maintenance commands",
    no_args_is_help=True,
)
cli.add_typer(docs_app, name="docs")


@docs_app.command(name="refresh-llm")
def docs_refresh_llm(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root directory",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Check for drift without modifying files (exit 1 on drift)",
    ),
) -> None:
    """Refresh marker-scoped AUTOGEN sections from deterministic command surface."""
    from taskx.docs.refresh_llm import MarkerStructureError, run_refresh_llm

    try:
        result = run_refresh_llm(
            repo_root=repo_root.resolve(),
            cli_app=cli,
            check=check,
        )
    except MarkerStructureError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(2) from exc
    except RuntimeError as exc:
        console.print(str(exc))
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    console.print("[green]✓ LLM docs refresh complete[/green]")
    console.print(f"[cyan]status:[/cyan] {result['status']}")
    console.print(f"[cyan]created:[/cyan] {len(result['created'])}")
    console.print(f"[cyan]modified:[/cyan] {len(result['modified'])}")
    console.print(f"[cyan]unchanged:[/cyan] {len(result['unchanged'])}")
    console.print(f"[cyan]refused:[/cyan] {len(result['refused'])}")
    console.print(f"[cyan]command_surface_hash:[/cyan] {result['command_surface_hash']}")

    if result["status"] == "refused":
        console.print("[yellow]Invalid AUTOGEN marker structure[/yellow]")
        raise typer.Exit(2)

    if check and result["status"] == "drift":
        raise typer.Exit(1)


# ============================================================================
# Route Commands
# ============================================================================

route_app = typer.Typer(
    name="route",
    help="Assisted deterministic routing commands",
    no_args_is_help=True,
)
cli.add_typer(route_app, name="route")


@route_app.command(name="init")
def route_init(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root path",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing availability.yaml",
    ),
) -> None:
    """Create repo-local route availability declaration."""
    try:
        created = ensure_default_availability(repo_root, force=force)
    except FileExistsError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        console.print("[yellow]Use --force to overwrite.[/yellow]")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    console.print("[green]✓ Route availability initialized[/green]")
    console.print(f"[cyan]Path:[/cyan] {created}")


@route_app.command(name="plan")
def route_plan(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root path",
    ),
    packet: Path = typer.Option(
        ...,
        "--packet",
        help="Task Packet markdown path",
    ),
    steps: list[str] = typer.Option(
        [],
        "--steps",
        help="Planned steps (repeatable and/or comma-separated)",
    ),
    out: Path = typer.Option(
        DEFAULT_PLAN_RELATIVE_PATH,
        "--out",
        help="Output path for ROUTE_PLAN.json",
    ),
    explain: bool = typer.Option(
        True,
        "--explain/--no-explain",
        help="Include step reasons in markdown report",
    ),
) -> None:
    """Build deterministic route plan artifacts from packet + availability."""
    try:
        def _do_plan():
            return build_route_plan(
                repo_root=repo_root,
                packet_path=packet,
                steps=parse_route_steps(steps),
            )

        plan = NeonSpinner("Planning route (no guessing)...").run(_do_plan)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    resolved_out = out if out.is_absolute() else (repo_root / out)
    resolved_out = resolved_out.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    plan_md_path = resolved_out.parent / "ROUTE_PLAN.md"

    plan_payload = route_plan_to_dict(plan)
    resolved_out.write_text(json.dumps(plan_payload, indent=2, sort_keys=True), encoding="utf-8")
    markdown = render_route_plan_markdown(plan)
    _ = explain
    plan_md_path.write_text(markdown, encoding="utf-8")

    console.print("[green]✓ Route plan written[/green]")
    console.print(f"[cyan]JSON:[/cyan] {resolved_out}")
    console.print(f"[cyan]Markdown:[/cyan] {plan_md_path}")

    if plan.status == "refused":
        if plan.refusal_reasons:
            console.print("[yellow]Route refused:[/yellow]")
            for reason in plan.refusal_reasons:
                console.print(f"[yellow]  - {reason}[/yellow]")
        raise typer.Exit(2)


@route_app.command(name="handoff")
def route_handoff(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root path",
    ),
    packet: Path = typer.Option(
        ...,
        "--packet",
        help="Task Packet markdown path",
    ),
    plan: Path | None = typer.Option(
        None,
        "--plan",
        help="Existing ROUTE_PLAN.json path (optional)",
    ),
    out: Path = typer.Option(
        Path("out/taskx_route/HANDOFF.md"),
        "--out",
        help="Output path for HANDOFF.md",
    ),
) -> None:
    """Generate deterministic handoff markdown (assisted only)."""
    try:
        if plan is None:
            plan_obj = build_route_plan(
                repo_root=repo_root,
                packet_path=packet,
                steps=parse_route_steps(None),
            )
        else:
            payload = json.loads(plan.resolve().read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError(f"Plan payload must be an object: {plan}")
            plan_obj = route_plan_from_dict(payload)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    resolved_out = out if out.is_absolute() else (repo_root / out)
    resolved_out = resolved_out.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    handoff_markdown = render_handoff_markdown(plan_obj)
    resolved_out.write_text(handoff_markdown, encoding="utf-8")
    typer.echo(handoff_markdown)
    typer.echo(f"Path: {resolved_out}")


@route_app.command(name="explain")
def route_explain(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root path",
    ),
    packet: Path | None = typer.Option(
        None,
        "--packet",
        help="Task Packet markdown path (required when --plan is not provided)",
    ),
    plan: Path | None = typer.Option(
        None,
        "--plan",
        help="Existing ROUTE_PLAN.json path (optional)",
    ),
    step: str = typer.Option(
        ...,
        "--step",
        help="Step name to explain",
    ),
) -> None:
    """Explain deterministic route scoring for a single step."""
    try:
        if plan is not None:
            payload = json.loads(plan.resolve().read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError(f"Plan payload must be an object: {plan}")
            planned = route_plan_from_dict(payload)
        else:
            if packet is None:
                raise RuntimeError("Either --packet or --plan is required")
            planned = build_route_plan(repo_root=repo_root, packet_path=packet, steps=parse_route_steps(None))

        explanation = explain_route_step(planned, step)
    except KeyError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    console.print(explanation)


@cli.command(name="orchestrate")
def orchestrate(
    packet: Path = typer.Argument(
        ...,
        help="Path to packet JSON",
    ),
) -> None:
    """Run TaskX orchestrator v0 for a packet."""
    outcome = orchestrate_packet(str(packet))
    status = str(outcome.get("status", "error"))
    run_dir = str(outcome.get("run_dir", ""))

    if status == "needs_handoff":
        handoff_stdout = str(outcome.get("stdout_text", "")).strip()
        if handoff_stdout:
            typer.echo(handoff_stdout)
        typer.echo(f"REFUSED run_dir={run_dir} reason=Manual handoff required")
        raise typer.Exit(2)

    if status == "ok":
        typer.echo(f"OK run_dir={run_dir}")
        raise typer.Exit(0)

    if status == "refused":
        reason = str(outcome.get("reason", "refused"))
        typer.echo(f"REFUSED run_dir={run_dir} reason={reason}")
        raise typer.Exit(2)

    typer.echo(f"ERROR run_dir={run_dir}")
    raise typer.Exit(1)


# ============================================================================
# PR Commands
# ============================================================================

pr_app = typer.Typer(
    name="pr",
    help="Assisted pull request flow commands",
    no_args_is_help=True,
)
cli.add_typer(pr_app, name="pr")


@pr_app.command(name="open")
def pr_open(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root path",
    ),
    title: str = typer.Option(
        ...,
        "--title",
        help="Pull request title",
    ),
    body_file: Path = typer.Option(
        ...,
        "--body-file",
        help="Pull request body markdown file",
    ),
    base: str = typer.Option(
        "main",
        "--base",
        help="Base branch name",
    ),
    remote: str = typer.Option(
        "origin",
        "--remote",
        help="Remote name for push and URL derivation",
    ),
    draft: bool = typer.Option(
        False,
        "--draft/--no-draft",
        help="Create draft PR when using gh",
    ),
    restore_branch: bool = typer.Option(
        True,
        "--restore-branch/--no-restore-branch",
        help="Restore original branch/HEAD after flow (success or failure)",
    ),
    allow_dirty: bool = typer.Option(
        False,
        "--allow-dirty",
        help="Allow dirty working tree (default refuses)",
    ),
    allow_detached: bool = typer.Option(
        False,
        "--allow-detached",
        help="Allow detached HEAD (default refuses)",
    ),
    allow_base_branch: bool = typer.Option(
        False,
        "--allow-base-branch",
        help="Allow running from base branch (default refuses)",
    ),
    refresh_llm: bool = typer.Option(
        False,
        "--refresh-llm/--no-refresh-llm",
        help="Run docs refresh-llm before push/PR and include result in report",
    ),
    require_branch_prefix: str = typer.Option(
        "codex/tp-pr-open-branch-guard",
        "--require-branch-prefix",
        help="Required branch prefix for branch isolation guard",
    ),
    allow_branch_prefix_override: bool = typer.Option(
        False,
        "--allow-branch-prefix-override",
        help="Allow bypassing branch prefix guard",
    ),
) -> None:
    """Open PR in assisted mode with restore rails and deterministic reports."""
    resolved_repo = repo_root.resolve()
    resolved_body = body_file if body_file.is_absolute() else (resolved_repo / body_file)
    resolved_body = resolved_body.resolve()

    def _refresh_runner(root: Path) -> dict[str, Any]:
        from taskx.docs.refresh_llm import MarkerStructureError, run_refresh_llm

        try:
            return run_refresh_llm(repo_root=root, cli_app=cli, check=False)
        except MarkerStructureError as exc:
            raise PrOpenRefusal("Refused: Invalid AUTOGEN marker structure") from exc

    try:
        report = run_pr_open(
            repo_root=resolved_repo,
            title=title,
            body_file=resolved_body,
            base=base,
            remote=remote,
            draft=draft,
            restore_branch=restore_branch,
            allow_dirty=allow_dirty,
            allow_detached=allow_detached,
            allow_base_branch=allow_base_branch,
            require_branch_prefix=require_branch_prefix,
            allow_branch_prefix_override=allow_branch_prefix_override,
            refresh_llm=refresh_llm,
            refresh_llm_runner=_refresh_runner if refresh_llm else None,
        )
    except PrOpenRefusal as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(2) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    report_dir = resolved_repo / "out" / "taskx_pr"
    console.print("[green]✓ PR open flow complete[/green]")
    console.print(f"[cyan]Status:[/cyan] {report['status']}")
    console.print(f"[cyan]PR URL:[/cyan] {report['pr_url']}")
    console.print(f"[cyan]Report JSON:[/cyan] {report_dir / 'PR_OPEN_REPORT.json'}")
    console.print(f"[cyan]Report MD:[/cyan] {report_dir / 'PR_OPEN_REPORT.md'}")


# ============================================================================
# Dopemux Adapter Commands
# ============================================================================

dopemux_app = typer.Typer(
    name="dopemux",
    help="Dopemux-integrated TaskX commands with automatic path detection",
    no_args_is_help=True,
)
cli.add_typer(dopemux_app, name="dopemux")

# Import dopemux adapter
try:
    from taskx_adapters.dopemux import (
        compute_dopemux_paths,
        detect_dopemux_root,
        select_run_folder,
    )
    DOPEMUX_AVAILABLE = True
except ImportError:
    DOPEMUX_AVAILABLE = False





def _require_dopemux() -> None:
    """Check if dopemux adapter is available."""
    if not DOPEMUX_AVAILABLE:
        console.print("[bold red]Error:[/bold red] dopemux adapter not available")
        console.print("Install with: pip install -e .[dopemux]")
        raise typer.Exit(1)


@dopemux_app.command(name="compile")
def dopemux_compile(
    mode: str = typer.Option(
        "mvp",
        help="Compilation mode: mvp, hardening, or full",
    ),
    max_packets: int | None = typer.Option(
        None,
        help="Maximum number of packets to compile",
    ),
    dopemux_root: Path | None = typer.Option(
        None,
        help="Override Dopemux root detection",
    ),
    out_root: Path | None = typer.Option(
        None,
        help="Override output root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Compile task packets with Dopemux path conventions."""
    _require_dopemux()
    _require_module(compile_task_queue, "task_compiler")
    _use_compat_options(project_root)

    # Detect Dopemux root and compute paths
    detection = detect_dopemux_root(override=dopemux_root)
    paths = compute_dopemux_paths(detection.root, out_root_override=out_root)
    canonical_mode = normalize_timestamp_mode(timestamp_mode)
    effective_run_id = make_run_id(prefix="RUN", timestamp_mode=canonical_mode)

    console.print(f"[cyan]Dopemux root:[/cyan] {detection.root} ({detection.marker_used})")
    console.print(f"[cyan]Run ID:[/cyan] {effective_run_id}")
    console.print(f"[cyan]Task queue output:[/cyan] {paths.task_queue_out}")

    # Resolve paths (assumes spec_mine structure)
    spec_path = detection.root / "spec_mine" / "MASTER_DESIGN_SPEC_V3.md"
    source_index_path = detection.root / "spec_mine" / "SOURCE_INDEX.json"

    if not spec_path.exists():
        console.print(f"[bold red]Error:[/bold red] Spec not found at {spec_path}")
        raise typer.Exit(1)
    if not source_index_path.exists():
        console.print(f"[bold red]Error:[/bold red] Source index not found at {source_index_path}")
        raise typer.Exit(1)

    # Ensure output directory exists
    paths.task_queue_out.mkdir(parents=True, exist_ok=True)

    try:
        compile_task_queue(
            spec_path=spec_path,
            source_index_path=source_index_path,
            output_dir=paths.task_queue_out,
            mode=mode,
            max_packets=max_packets if max_packets else 100,
            seed=42,  # Fixed seed for CLI
            pipeline_version=__version__,
            timestamp_mode=timestamp_mode,
        )
        console.print(f"[green]✓ Task packets compiled to {paths.task_queue_out}[/green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@dopemux_app.command(name="run")
def dopemux_run(
    task_id: str = typer.Option(
        ...,
        help="Task packet ID to execute",
    ),
    run_id: str | None = typer.Option(
        None,
        help="Run identifier (auto-generated if not provided)",
    ),
    dopemux_root: Path | None = typer.Option(
        None,
        help="Override Dopemux root detection",
    ),
    out_root: Path | None = typer.Option(
        None,
        help="Override output root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Execute a task packet (create run workspace)."""
    _require_dopemux()
    _require_module(create_run_workspace, "task_runner")
    _use_compat_options(project_root)

    # Detect Dopemux root and compute paths
    detection = detect_dopemux_root(override=dopemux_root)
    paths = compute_dopemux_paths(detection.root, out_root_override=out_root)
    canonical_mode = normalize_timestamp_mode(timestamp_mode)
    pipeline_timestamp_mode = to_pipeline_timestamp_mode(timestamp_mode)
    effective_run_id = run_id or make_run_id(prefix="RUN", timestamp_mode=canonical_mode)

    console.print(f"[cyan]Dopemux root:[/cyan] {detection.root} ({detection.marker_used})")

    # Find packet
    task_packets_dir = paths.task_queue_out / "TASK_PACKETS"
    if not task_packets_dir.exists():
         console.print(f"[bold red]Error:[/bold red] Could not locate TASK_PACKETS directory at {task_packets_dir}")
         raise typer.Exit(1)

    candidates = list(task_packets_dir.glob(f"{task_id}_*.md"))
    if not candidates:
        console.print(f"[bold red]Error:[/bold red] Task packet {task_id} not found in {task_packets_dir}")
        raise typer.Exit(1)

    packet_path = candidates[0].resolve()
    paths.runs_out.mkdir(parents=True, exist_ok=True)

    try:
        result = create_run_workspace(
            task_packet_path=packet_path,
            output_dir=paths.runs_out,
            run_id=effective_run_id,
            timestamp_mode=pipeline_timestamp_mode,
            pipeline_version=__version__,
        )
        console.print(f"[green]✓ Workspace created at: {result['run_dir']}[/green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@dopemux_app.command(name="collect")
def dopemux_collect(
    run: Path | None = typer.Option(
        None,
        help="Specific run folder (auto-selects most recent if not provided)",
    ),
    max_claims: int = typer.Option(
        100,
        help="Maximum claims to collect",
    ),
    max_evidence_chars: int = typer.Option(
        50000,
        help="Maximum evidence characters",
    ),
    dopemux_root: Path | None = typer.Option(
        None,
        help="Override Dopemux root detection",
    ),
    out_root: Path | None = typer.Option(
        None,
        help="Override output root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Collect evidence with Dopemux path conventions."""
    _require_dopemux()
    _require_module(collect_evidence_impl, "evidence")
    _use_compat_options(project_root)

    # Detect Dopemux root and compute paths
    detection = detect_dopemux_root(override=dopemux_root)
    paths = compute_dopemux_paths(detection.root, out_root_override=out_root)

    # Select run folder
    selected_run = select_run_folder(paths.runs_out, run)

    console.print(f"[cyan]Dopemux root:[/cyan] {detection.root} ({detection.marker_used})")
    console.print(f"[cyan]Collecting from:[/cyan] {selected_run}")

    try:
        collect_evidence_impl(
            run_dir=selected_run,
            max_claims=max_claims,
            max_evidence_chars=max_evidence_chars,
            timestamp_mode=timestamp_mode,
            pipeline_version=__version__,
        )
        console.print("[green]✓ Evidence collected[/green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@dopemux_app.command(name="gate")
def dopemux_gate(
    run: Path | None = typer.Option(
        None,
        help="Specific run folder (auto-selects most recent if not provided)",
    ),
    diff_mode: str = typer.Option(
        "auto",
        help="Diff mode: git, fs, or auto",
    ),
    require_verification_evidence: bool = typer.Option(
        True,
        help="Require verification evidence",
    ),
    dopemux_root: Path | None = typer.Option(
        None,
        help="Override Dopemux root detection",
    ),
    out_root: Path | None = typer.Option(
        None,
        help="Override output root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Run allowlist gate with Dopemux path conventions."""
    _require_dopemux()
    _require_module(run_allowlist_gate, "compliance")
    _use_compat_options(project_root)

    # Detect Dopemux root and compute paths
    detection = detect_dopemux_root(override=dopemux_root)
    paths = compute_dopemux_paths(detection.root, out_root_override=out_root)

    # Select run folder
    selected_run = select_run_folder(paths.runs_out, run)

    console.print(f"[cyan]Dopemux root:[/cyan] {detection.root} ({detection.marker_used})")
    console.print(f"[cyan]Gating run:[/cyan] {selected_run}")

    try:
        result = run_allowlist_gate(
            run_dir=selected_run,
            repo_root=detection.root,
            timestamp_mode=timestamp_mode,
            require_verification_evidence=require_verification_evidence,
            diff_mode=diff_mode,
        )

        if not result.violations:
            console.print("[green]✓ Allowlist gate passed[/green]")
            raise typer.Exit(0)
        else:
            console.print(f"[red]✗ Allowlist gate failed ({len(result.violations)} violations)[/red]")
            for v in result.violations:
                console.print(f"[red]  - {v.type}: {v.message}[/red]")
            raise typer.Exit(2)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@dopemux_app.command(name="promote")
def dopemux_promote(
    run: Path | None = typer.Option(
        None,
        help="Specific run folder (auto-selects most recent if not provided)",
    ),
    require_run_summary: bool = typer.Option(
        True,
        help="Require run summary for promotion",
    ),
    dopemux_root: Path | None = typer.Option(
        None,
        help="Override Dopemux root detection",
    ),
    out_root: Path | None = typer.Option(
        None,
        help="Override output root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Promote a run with Dopemux path conventions."""
    _require_dopemux()
    _require_module(promote_run_impl, "promotion")
    _use_compat_options(project_root)

    # Detect Dopemux root and compute paths
    detection = detect_dopemux_root(override=dopemux_root)
    paths = compute_dopemux_paths(detection.root, out_root_override=out_root)

    # Select run folder
    selected_run = select_run_folder(paths.runs_out, run)

    console.print(f"[cyan]Dopemux root:[/cyan] {detection.root} ({detection.marker_used})")
    console.print(f"[cyan]Promoting run:[/cyan] {selected_run}")

    try:
        result = promote_run_impl(
            run_dir=selected_run,
            require_run_summary=require_run_summary,
            timestamp_mode=timestamp_mode,
        )

        if result.status == "passed":
            console.print("[green]✓ Run promoted[/green]")
            raise typer.Exit(0)
        else:
            console.print("[red]✗ Promotion denied[/red]")
            raise typer.Exit(2)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@dopemux_app.command(name="feedback")
def dopemux_feedback(
    require_promotion: bool = typer.Option(
        True,
        help="Only process promoted runs",
    ),
    dopemux_root: Path | None = typer.Option(
        None,
        help="Override Dopemux root detection",
    ),
    out_root: Path | None = typer.Option(
        None,
        help="Override output root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Generate spec feedback with Dopemux path conventions."""
    _require_dopemux()
    _require_module(generate_spec_feedback, "spec_feedback")
    _use_compat_options(project_root)

    # Detect Dopemux root and compute paths
    detection = detect_dopemux_root(override=dopemux_root)
    paths = compute_dopemux_paths(detection.root, out_root_override=out_root)

    console.print(f"[cyan]Dopemux root:[/cyan] {detection.root} ({detection.marker_used})")
    console.print(f"[cyan]Runs directory:[/cyan] {paths.runs_out}")
    console.print(f"[cyan]Task queue:[/cyan] {paths.task_queue_default}")
    console.print(f"[cyan]Feedback output:[/cyan] {paths.spec_feedback_out}")

    # Ensure output directory exists
    paths.spec_feedback_out.mkdir(parents=True, exist_ok=True)

    try:
        # Filter runs if required
        target_runs = []
        for run_dir in paths.runs_out.iterdir():
            if not run_dir.is_dir():
                continue
            if require_promotion and not (run_dir / "PROMOTION.json").exists():
                continue
            target_runs.append(run_dir)

        generate_spec_feedback(
            run_paths=target_runs,
            task_queue_path=paths.task_queue_default,
            output_dir=paths.spec_feedback_out,
            timestamp_mode=timestamp_mode,
        )
        console.print("[green]✓ Spec feedback generated[/green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@dopemux_app.command(name="loop")
def dopemux_loop(
    loop_id: str | None = typer.Option(
        None,
        help="Loop identifier (auto-generated if not provided)",
    ),
    mode: str = typer.Option(
        "mvp",
        help="Loop mode: mvp, hardening, or full",
    ),
    run_task: str | None = typer.Option(
        None,
        help="Specific task ID to run in loop",
    ),
    collect_evidence: bool = typer.Option(
        True,
        help="Collect evidence after task execution",
    ),
    feedback: bool = typer.Option(
        True,
        help="Generate feedback after runs",
    ),
    max_packets: int = typer.Option(
        5,
        help="Maximum task packets to process",
    ),
    seed: int = typer.Option(
        42,
        help="Random seed for ordering",
    ),
    dopemux_root: Path | None = typer.Option(
        None,
        help="Override Dopemux root detection",
    ),
    out_root: Path | None = typer.Option(
        None,
        help="Override output root directory",
    ),
    project_root: Path | None = typer.Option(
        None,
        help="Project root directory",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Run complete lifecycle loop with Dopemux path conventions."""
    _require_dopemux()
    _use_compat_options(project_root)

    if not LOOP_AVAILABLE:
        console.print("[bold red]Error:[/bold red] loop module not installed in this TaskX build")
        raise typer.Exit(1)

    _require_module(run_loop, "loop")

    # Detect Dopemux root and compute paths
    detection = detect_dopemux_root(override=dopemux_root)
    paths = compute_dopemux_paths(detection.root, out_root_override=out_root)

    console.print(f"[cyan]Dopemux root:[/cyan] {detection.root} ({detection.marker_used})")
    console.print(f"[cyan]Loop output:[/cyan] {paths.loop_out}")

    # Ensure output directory exists
    paths.loop_out.mkdir(parents=True, exist_ok=True)

    try:
        inputs = LoopInputs(
            root=detection.root,
            mode=mode,
            max_packets=max_packets,
            seed=seed,
            run_task=run_task,
            run_id=None,
            collect_evidence=collect_evidence,
            feedback=feedback,
        )

        run_loop(
            loop_id=loop_id if loop_id else "LOOP_AUTO",
            loop_dir=paths.loop_out,
            inputs=inputs,
            timestamp_mode=timestamp_mode,
        )
        console.print("[green]✓ Loop execution complete[/green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e


@cli.command(name="doctor")
def doctor_cmd(
    out: Path = typer.Option(
        Path("./out/taskx_doctor"),
        "--out",
        "-o",
        help="Output directory for doctor reports"
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        "--timestamp-mode",
        help="Timestamp mode: deterministic or wallclock"
    ),
    require_git: bool = typer.Option(
        False,
        "--require-git",
        help="Fail if git is not available"
    ),
    repo_root: Path | None = typer.Option(
        None,
        "--repo-root",
        help="Override repository root path"
    ),
    project_root: Path | None = typer.Option(
        None,
        "--project-root",
        help="Override project root path"
    ),
) -> None:
    """Run installation integrity checks and generate DOCTOR_REPORT.

    Validates that TaskX is correctly installed with all required schemas
    bundled and accessible. Useful for diagnosing packaging issues.

    Exit codes:
      0 - All checks passed
      2 - One or more checks failed
      1 - Tooling error
    """
    from taskx.doctor import run_doctor

    try:
        report = run_doctor(
            out_dir=out,
            timestamp_mode=timestamp_mode,
            require_git=require_git,
            repo_root=repo_root,
            project_root=project_root
        )

        # Print summary
        typer.echo("\nTaskX Doctor Report")
        typer.echo(f"Status: {report.status.upper()}")
        typer.echo("\nChecks:")
        typer.echo(f"  Passed: {report.checks['passed']}")
        typer.echo(f"  Failed: {report.checks['failed']}")
        typer.echo(f"  Warnings: {report.checks['warnings']}")
        typer.echo("\nReports written to:")
        typer.echo(f"  {out / 'DOCTOR_REPORT.json'}")
        typer.echo(f"  {out / 'DOCTOR_REPORT.md'}")

        # Exit with appropriate code
        if report.status == "failed":
            typer.echo("\n❌ Some checks failed. See report for details.")
            raise typer.Exit(code=2)
        else:
            typer.echo("\n✅ All checks passed.")
            raise typer.Exit(code=0)

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"❌ Doctor run failed: {e}", err=True)
        raise typer.Exit(code=1) from e


@cli.command(name="ci-gate")
def ci_gate_cmd(
    out: Path | None = typer.Option(
        None,
        "--out",
        "-o",
        help="Deprecated. CI gate reports are written inside the selected run directory.",
        hidden=True,
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        "--timestamp-mode",
        help="Timestamp mode: deterministic, now, or wallclock"
    ),
    require_git: bool = typer.Option(
        False,
        "--require-git",
        help="Fail if git is not available"
    ),
    run: Path | None = typer.Option(
        None,
        "--run",
        help="Run directory to validate (default <run-root>/<run-id>)",
    ),
    run_root: Path | None = typer.Option(
        None,
        "--run-root",
        help="Run root used when --run is omitted",
    ),
    runs_root: Path | None = typer.Option(
        None,
        "--runs-root",
        help="Deprecated alias for --run-root",
        hidden=True,
    ),
    promotion_filename: str = typer.Option(
        PROMOTION_TOKEN_FILENAME,
        "--promotion-filename",
        help="Name of promotion file to validate"
    ),
    require_promotion: bool = typer.Option(
        True,
        "--require-promotion",
        help="Whether to require promotion validation"
    ),
    require_promotion_passed: bool = typer.Option(
        True,
        "--require-promotion-passed",
        help="Whether to require promotion status == 'passed'"
    ),
    no_repo_guard: bool = typer.Option(
        False,
        "--no-repo-guard",
        help="Skip TaskX repo detection (use with caution)",
    ),
    manifest: bool = typer.Option(
        False,
        "--manifest",
        help="Initialize manifest if missing and append this command record",
    ),
    rescue_patch: str | None = typer.Option(
        None,
        "--rescue-patch",
        help="Write a rescue patch on guard failure (path or 'auto')",
    ),
) -> None:
    """Run CI gate checks (doctor + promotion validation).

    Combines TaskX installation health checks with run promotion validation
    for use in CI/CD pipelines. Ensures both the environment is sane and
    that runs have valid promotion tokens.

    Exit codes:
      0 - All checks passed
      2 - One or more checks failed (policy violation)
      1 - Tooling error
    """
    from taskx.ci_gate import run_ci_gate

    selected_run: Path | None = None
    manifest_enabled = False
    manifest_started_at = get_manifest_timestamp("deterministic")
    manifest_stdout: list[str] = []
    manifest_stderr: list[str] = []
    manifest_exit_code = 1

    try:
        manifest_started_at = get_manifest_timestamp(normalize_timestamp_mode(timestamp_mode))
        _check_repo_guard(no_repo_guard, rescue_patch=rescue_patch)
        selected_run = _resolve_stateful_run_dir(run, run_root or runs_root, timestamp_mode).resolve()
        manifest_enabled = _ensure_manifest_ready(
            selected_run,
            create_if_missing=manifest,
            mode="ACT",
            timestamp_mode=timestamp_mode,
        )
        pipeline_timestamp_mode = to_pipeline_timestamp_mode(timestamp_mode)
        effective_promotion_filename = promotion_filename
        canonical_promotion_path = selected_run / PROMOTION_TOKEN_FILENAME
        legacy_promotion_path = selected_run / PROMOTION_LEGACY_FILENAME
        if (
            promotion_filename == PROMOTION_TOKEN_FILENAME
            and not canonical_promotion_path.exists()
            and legacy_promotion_path.exists()
        ):
            effective_promotion_filename = PROMOTION_LEGACY_FILENAME
        if out is not None:
            typer.echo("⚠️  --out is deprecated; writing CI gate reports under the selected run directory.")

        report = run_ci_gate(
            out_dir=selected_run,
            timestamp_mode=pipeline_timestamp_mode,
            require_git=require_git,
            run_dir=selected_run,
            runs_root=None,
            promotion_filename=effective_promotion_filename,
            require_promotion=require_promotion,
            require_promotion_passed=require_promotion_passed
        )

        # Print summary
        typer.echo("\nTaskX CI Gate Report")
        typer.echo(f"Status: {report.status.upper()}")
        typer.echo(f"\nDoctor: {report.doctor['status']}")
        manifest_stdout.append(f"CI gate status: {report.status}")
        manifest_stdout.append(f"Doctor status: {report.doctor['status']}")

        if report.promotion["required"]:
            promo_status = "✅ Validated" if report.promotion["validated"] else "❌ Failed"
            typer.echo(f"Promotion: {promo_status}")
            manifest_stdout.append(f"Promotion validated: {report.promotion['validated']}")
            if report.promotion["run_dir"]:
                typer.echo(f"  Run: {report.promotion['run_dir']}")
        else:
            typer.echo("Promotion: Not required")
            manifest_stdout.append("Promotion validation skipped")

        typer.echo("\nChecks:")
        typer.echo(f"  Passed: {report.checks['passed']}")
        typer.echo(f"  Failed: {report.checks['failed']}")
        typer.echo(f"  Warnings: {report.checks['warnings']}")
        manifest_stdout.append(
            f"Checks passed={report.checks['passed']} failed={report.checks['failed']} warnings={report.checks['warnings']}"
        )

        typer.echo("\nReports written to:")
        typer.echo(f"  {selected_run / 'CI_GATE_REPORT.json'}")
        typer.echo(f"  {selected_run / 'CI_GATE_REPORT.md'}")

        # Exit with appropriate code
        if report.status == "failed":
            typer.echo("\n❌ CI gate failed.")
            raise typer.Exit(code=2)
        else:
            typer.echo("\n✅ CI gate passed.")
            raise typer.Exit(code=0)

    except typer.Exit as exc:
        manifest_exit_code = int(exc.exit_code)
        raise
    except Exception as e:
        manifest_stderr.append(str(e))
        typer.echo(f"❌ CI gate run failed: {e}", err=True)
        raise typer.Exit(code=1) from e
    finally:
        ci_gate_artifacts = []
        if selected_run is not None:
            ci_gate_artifacts = [
                _artifact_ref_for_run(selected_run, selected_run / "CI_GATE_REPORT.json"),
                _artifact_ref_for_run(selected_run, selected_run / "CI_GATE_REPORT.md"),
                _artifact_ref_for_run(selected_run, selected_run / "doctor" / "DOCTOR_REPORT.json"),
                _artifact_ref_for_run(selected_run, selected_run / "doctor" / "DOCTOR_REPORT.md"),
            ]
        _append_manifest_command(
            enabled=manifest_enabled,
            run_dir=selected_run,
            timestamp_mode=timestamp_mode,
            exit_code=manifest_exit_code,
            started_at=manifest_started_at,
            stdout_lines=manifest_stdout,
            stderr_lines=manifest_stderr,
            expected_artifacts=ci_gate_artifacts,
        )



class ProjectPreset(str, Enum):
    """Supported directive presets for project init."""

    TASKX = "taskx"
    CHATX = "chatx"
    BOTH = "both"
    NONE = "none"


class ProjectPack(str, Enum):
    """Supported directive packs for project toggles."""

    TASKX = "taskx"
    CHATX = "chatx"


class ProjectMode(str, Enum):
    """Supported master modes."""

    TASKX = "taskx"
    CHATX = "chatx"
    BOTH = "both"
    NONE = "none"


project_app = typer.Typer(
    name="project",
    help="Project file initialization and directive pack toggles",
    no_args_is_help=True,
)
cli.add_typer(project_app, name="project")

project_mode_app = typer.Typer(
    name="mode",
    help="Master mode operations across TaskX/ChatX packs",
    no_args_is_help=True,
)
project_app.add_typer(project_mode_app, name="mode")

project_shell_app = typer.Typer(
    name="shell",
    help="Repo-local shell wiring helpers",
    no_args_is_help=True,
)
project_app.add_typer(project_shell_app, name="shell")


@project_app.command(name="init")
def project_init(
    out: Path = typer.Option(
        ...,
        "--out",
        help="Project directory to initialize/update",
    ),
    preset: ProjectPreset = typer.Option(
        ProjectPreset.TASKX,
        "--preset",
        help="Directive pack preset to apply",
    ),
) -> None:
    """Generate or safely update project-facing instruction files."""
    from taskx.project.init import init_project

    try:
        result = init_project(out_dir=out, preset=preset.value)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Project init failed: {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[green]✓ Project initialized[/green] at {result['out_dir']}")
    console.print(f"[cyan]Preset:[/cyan] {result['preset']}")
    console.print(f"[cyan]Report:[/cyan] {result['report_path']}")


@project_app.command(name="enable")
def project_enable(
    pack: ProjectPack = typer.Argument(..., help="Directive pack to enable"),
    path: Path = typer.Option(
        ...,
        "--path",
        help="Project directory",
    ),
) -> None:
    """Enable a directive pack across managed project files."""
    from taskx.project.toggles import enable_pack

    try:
        result = enable_pack(project_dir=path, pack_name=pack.value)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Enable failed: {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[green]✓ Enabled {result['pack']}[/green] in {result['project_dir']}")
    console.print(f"[cyan]Report:[/cyan] {result['report_path']}")


@project_app.command(name="disable")
def project_disable(
    pack: ProjectPack = typer.Argument(..., help="Directive pack to disable"),
    path: Path = typer.Option(
        ...,
        "--path",
        help="Project directory",
    ),
) -> None:
    """Disable a directive pack across managed project files."""
    from taskx.project.toggles import disable_pack

    try:
        result = disable_pack(project_dir=path, pack_name=pack.value)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Disable failed: {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[green]✓ Disabled {result['pack']}[/green] in {result['project_dir']}")
    console.print(f"[cyan]Report:[/cyan] {result['report_path']}")


@project_app.command(name="status")
def project_status_cmd(
    path: Path = typer.Option(
        ...,
        "--path",
        help="Project directory",
    ),
) -> None:
    """Show directive pack status for each managed file."""
    from taskx.project.toggles import project_status

    result = project_status(project_dir=path)
    console.print(f"[cyan]Project:[/cyan] {result['project_dir']}")
    for file_info in result["files"]:
        file_name = Path(file_info["file"]).name
        if not file_info["exists"]:
            console.print(f"[yellow]- {file_name}: missing[/yellow]")
            continue
        taskx_state = "enabled" if file_info["packs"]["taskx"] else "disabled"
        chatx_state = "enabled" if file_info["packs"]["chatx"] else "disabled"
        console.print(f"- {file_name}: taskx={taskx_state}, chatx={chatx_state}")


@project_mode_app.command(name="set")
def project_mode_set(
    path: Path = typer.Option(
        ...,
        "--path",
        help="Project directory",
    ),
    mode: ProjectMode = typer.Option(
        ...,
        "--mode",
        help="Master mode: taskx, chatx, both, or none",
    ),
) -> None:
    """Set both directive packs in a single idempotent operation."""
    from taskx.project.mode import set_mode

    try:
        result = set_mode(project_dir=path, mode=mode.value)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Mode set failed: {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[green]✓ Applied mode '{result['mode']}'[/green] for {path}")
    for filename in sorted(result["per_file_status"]):
        state = result["per_file_status"][filename]
        console.print(f"- {filename}: taskx={state['taskx']}, chatx={state['chatx']}")
    console.print(f"[cyan]Files changed:[/cyan] {len(result['changed_files'])}")
    console.print(f"[cyan]Report:[/cyan] {result['report_path']}")


@project_app.command(name="doctor")
def project_doctor_cmd(
    path: Path = typer.Option(
        ...,
        "--path",
        help="Project directory",
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Apply deterministic repairs before re-checking",
    ),
    mode: ProjectMode | None = typer.Option(
        None,
        "--mode",
        help="Override target mode used by --fix",
    ),
) -> None:
    """Check (and optionally fix) TaskX/ChatX project readiness."""
    from taskx.project.doctor import (
        check_project,
        fix_project,
        render_doctor_summary,
        write_doctor_reports,
    )

    requested_mode = mode.value if mode is not None else None

    try:
        report = fix_project(path, requested_mode) if fix else check_project(path)
        report_paths = write_doctor_reports(path, report)
    except ValueError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Project doctor failed: {exc}")
        raise typer.Exit(1) from exc

    console.print(render_doctor_summary(report))
    console.print(f"[cyan]Reports:[/cyan] {report_paths['markdown']}, {report_paths['json']}")

    if report["status"] == "fail":
        raise typer.Exit(2)
    raise typer.Exit(0)


@project_app.command(name="upgrade")
def project_upgrade_cmd(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root to upgrade/stabilize",
    ),
    instructions_path: Path = typer.Option(
        Path(".taskx/instructions"),
        "--instructions-path",
        help="Instruction directory for project doctor --fix",
    ),
    mode: ProjectMode = typer.Option(
        ProjectMode.BOTH,
        "--mode",
        help="Master mode: taskx, chatx, both, or none",
    ),
    shell: bool = typer.Option(
        True,
        "--shell/--no-shell",
        help="Run project shell init",
    ),
    packs: bool = typer.Option(
        True,
        "--packs/--no-packs",
        help="Run project doctor --fix for instruction packs",
    ),
    doctor: bool = typer.Option(
        True,
        "--doctor/--no-doctor",
        help="Run taskx doctor after upgrade actions",
    ),
    allow_init_rails: bool = typer.Option(
        False,
        "--allow-init-rails",
        help="Initialize missing .taskxroot/.taskx/project.json rails",
    ),
) -> None:
    """Run deterministic project stabilization flow in one command."""
    from taskx.project.upgrade import ProjectUpgradeRefusalError, run_project_upgrade

    try:
        report = run_project_upgrade(
            repo_root=repo_root,
            instructions_path=instructions_path,
            mode=mode.value,
            shell=shell,
            packs=packs,
            doctor=doctor,
            allow_init_rails=allow_init_rails,
        )
    except ProjectUpgradeRefusalError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        raise typer.Exit(2) from exc
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Project upgrade failed: {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[green]✓ Project upgrade complete[/green] at {report['repo_root']}")
    console.print(
        f"[cyan]Rails:[/cyan] status={report['rails_state']['status']} "
        f"project_id={report['rails_state']['project_id']}"
    )

    changes = report["file_changes"]
    console.print(
        f"[cyan]Changes:[/cyan] created={len(changes['created'])} "
        f"modified={len(changes['modified'])} deleted={len(changes['deleted'])}"
    )

    if report.get("doctor") is not None:
        console.print(
            f"[cyan]Doctor:[/cyan] status={report['doctor']['status']} "
            f"warnings={report['doctor']['checks']['warnings']}"
        )

    console.print(
        f"[cyan]Report:[/cyan] {report['report_paths']['markdown']}, {report['report_paths']['json']}"
    )


@project_shell_app.command(name="init")
def project_shell_init_cmd(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root to initialize",
    ),
) -> None:
    """Initialize repo-local shell wiring (.envrc + scripts/taskx shims)."""
    from taskx.project.shell import init_shell

    try:
        report = init_shell(repo_root)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Project shell init failed: {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[green]✓ Project shell initialized[/green] at {report['repo_root']}")
    console.print(
        f"[cyan]Created:[/cyan] {len(report['created_files'])} "
        f"[cyan]Skipped:[/cyan] {len(report['skipped_files'])}"
    )
    for file_state in report["files"]:
        marker = "[green]ok[/green]" if file_state["valid"] else "[yellow]needs-attention[/yellow]"
        console.print(f"- {file_state['path']}: {marker}")
    console.print(f"[cyan]Direnv found:[/cyan] {report['direnv_found']}")
    console.print(
        f"[cyan]Report:[/cyan] {report['report_paths']['markdown']}, {report['report_paths']['json']}"
    )
    console.print("[cyan]Next steps:[/cyan]")
    for step in report["next_steps"]:
        console.print(f"- {step}")


@project_shell_app.command(name="status")
def project_shell_status_cmd(
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root to inspect",
    ),
) -> None:
    """Report repo-local shell wiring status."""
    from taskx.project.shell import status_shell

    try:
        report = status_shell(repo_root)
    except Exception as exc:
        console.print(f"[bold red]Error:[/bold red] Project shell status failed: {exc}")
        raise typer.Exit(1) from exc

    console.print(f"[cyan]Repo:[/cyan] {report['repo_root']}")
    for file_state in report["files"]:
        exists = "present" if file_state["exists"] else "missing"
        if file_state["valid"]:
            state = "[green]valid[/green]"
        elif file_state["exists"]:
            state = "[yellow]present-but-invalid[/yellow]"
        else:
            state = "[yellow]missing[/yellow]"
        console.print(f"- {file_state['path']}: {exists}, {state}")
    console.print(f"[cyan]Direnv found:[/cyan] {report['direnv_found']}")
    console.print(
        f"[cyan]Report:[/cyan] {report['report_paths']['markdown']}, {report['report_paths']['json']}"
    )
    console.print("[cyan]Next steps:[/cyan]")
    for step in report["next_steps"]:
        console.print(f"- {step}")


# Bundle Commands

bundle_app = typer.Typer(
    name="bundle",
    help="Case bundle management commands",
    no_args_is_help=True,
)


@bundle_app.command(name="export")
def bundle_export(
    last: int = typer.Option(10, help="Number of recent runs/packets to include"),
    out: Path = typer.Option(Path("./out/bundles"), help="Output directory for bundles"),
    case_id: str | None = typer.Option(None, help="Specific case ID (auto-generated if empty)"),
    config: Path | None = typer.Option(None, help="Path to bundle config yaml"),
) -> None:
    """Export a deterministic case bundle."""
    _require_module(BundleExporter, "bundle_exporter")

    console.print(f"[cyan]Exporting last {last} items...[/cyan]")

    try:
        # Detect repo root (naive: current dir)
        repo_root = Path.cwd()
        exporter = BundleExporter(repo_root=repo_root, config_path=config)
        exporter.export(last_n=last, out_dir=out, case_id=case_id)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Bundle export failed: {e}")
        raise typer.Exit(1) from e


@bundle_app.command(name="ingest")
def bundle_ingest(
    zip_path: Path = typer.Option(..., "--zip", help="Path to CASE_*.zip bundle"),
    out: Path = typer.Option(Path("./out/cases"), "--out", help="Output directory for cases"),
    timestamp_mode: str = typer.Option(
        "deterministic",
        "--timestamp-mode",
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Ingest a case bundle and generate CASE_INDEX + ingest report."""
    _require_module(ingest_bundle_impl, "bundle_ingester")

    try:
        result = ingest_bundle_impl(zip_path=zip_path, output_dir=out, timestamp_mode=timestamp_mode)
        typer.echo("Case bundle ingestion complete")
        typer.echo(f"Integrity: {result['integrity_status']}")
        typer.echo(f"Case dir: {result['case_dir']}")
        typer.echo(f"CASE_INDEX.json: {result['case_index']}")
        typer.echo(f"CASE_INGEST_REPORT.md: {result['ingest_report']}")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Bundle ingest failed: {e}")
        raise typer.Exit(1) from e


cli.add_typer(bundle_app, name="bundle")


case_app = typer.Typer(
    name="case",
    help="Case audit commands",
    no_args_is_help=True,
)


@case_app.command(name="audit")
def case_audit(
    case_dir: Path = typer.Option(..., "--case", help="Path to ingested case directory"),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Output directory for audit artifacts (default: <case>/reports)",
    ),
    timestamp_mode: str = typer.Option(
        "deterministic",
        "--timestamp-mode",
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Run deterministic audit on an ingested case directory."""
    _require_module(audit_case_impl, "case_auditor")
    audit_out = out if out else (case_dir / "reports")

    try:
        result = audit_case_impl(case_dir=case_dir, output_dir=audit_out, timestamp_mode=timestamp_mode)
        typer.echo("Case audit complete")
        typer.echo(f"CASE_FINDINGS.json: {result['findings']}")
        typer.echo(f"CASE_AUDIT_REPORT.md: {result['report']}")
        typer.echo(f"PACKET_RECOMMENDATIONS.json: {result['recommendations']}")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Case audit failed: {e}")
        raise typer.Exit(1) from e


cli.add_typer(case_app, name="case")


if __name__ == "__main__":

    cli()
