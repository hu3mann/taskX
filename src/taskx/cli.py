"""TaskX Ultra-Min CLI - Task Packet Lifecycle Commands Only."""

from pathlib import Path

import typer
from rich.console import Console

from typing import Any

from taskx import __version__


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


cli = typer.Typer(
    name="taskx",
    help="TaskX - Minimal Task Packet Lifecycle CLI",
    no_args_is_help=True,
)
console = Console()


def _check_repo_guard(bypass: bool) -> Path:
    """
    Check TaskX repo guard unless bypassed.

    Args:
        bypass: If True, skip guard check and warn user

    Returns:
        Path to detected repo root (or cwd if bypassed)

    Raises:
        RuntimeError: If guard check fails and not bypassed
    """
    from taskx.utils.repo import require_taskx_repo_root

    if bypass:
        console.print(
            "[bold yellow]⚠️  WARNING: Repo guard bypassed![/bold yellow]\n"
            "[yellow]Running stateful command without TaskX repo detection.[/yellow]"
        )
        return Path.cwd()

    # Will raise RuntimeError with helpful message if not in TaskX repo
    return require_taskx_repo_root(Path.cwd())


def _require_module(module_func: Any, module_name: str) -> None:
    """Check if a required module is available."""
    if module_func is None:
        console.print(f"[bold red]Error:[/bold red] {module_name} module not available in this TaskX build")
        raise typer.Exit(1)


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
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Compile task packets from spec."""
    _require_module(compile_task_queue, "task_compiler")

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
        raise typer.Exit(1)


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
    out: Path = typer.Option(
        Path("./out/runs"),
        help="Output directory for run artifacts",
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
    """Execute a task packet (create run workspace)."""
    _require_module(create_run_workspace, "task_runner")

    console.print(f"[cyan]Preparing run for task: {task_id}[/cyan]")

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
    
    packet_path = candidates[0]

    try:
        result = create_run_workspace(
            task_packet_path=packet_path,
            output_dir=out,
            run_id=None,
            timestamp_mode=timestamp_mode,
            pipeline_version=__version__,
        )
        console.print(f"[green]✓ Workpace created at: {result['run_dir']}[/green]")
        console.print(f"[cyan]To implement:[/cyan] Follow instructions in PLAN.md")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


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
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Collect verification evidence from a task run."""
    _require_module(collect_evidence_impl, "evidence")

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
        raise typer.Exit(1)


@cli.command()
def gate_allowlist(
    run: Path = typer.Option(
        ...,
        help="Path to run directory",
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
        help="Timestamp mode: deterministic or wallclock",
    ),
    no_repo_guard: bool = typer.Option(
        False,
        "--no-repo-guard",
        help="Skip TaskX repo detection (use with caution)",
    ),
) -> None:
    """Run allowlist compliance gate on a task run."""
    _require_module(run_allowlist_gate, "compliance")

    # Guard check
    _check_repo_guard(no_repo_guard)

    console.print("[cyan]Running allowlist gate...[/cyan]")

    try:
        # Resolve repo root
        effective_repo_root = repo_root or _check_repo_guard(no_repo_guard)

        result = run_allowlist_gate(
            run_dir=run,
            repo_root=effective_repo_root,
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
        raise typer.Exit(1)


@cli.command()
def promote_run(
    run: Path = typer.Option(
        ...,
        help="Path to run directory",
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
        help="Timestamp mode: deterministic or wallclock",
    ),
    no_repo_guard: bool = typer.Option(
        False,
        "--no-repo-guard",
        help="Skip TaskX repo detection (use with caution)",
    ),
) -> None:
    """Promote a task run by issuing completion token."""
    _require_module(promote_run_impl, "promotion")

    # Guard check
    _check_repo_guard(no_repo_guard)

    console.print("[cyan]Promoting run...[/cyan]")

    try:
        result = promote_run_impl(
            run_dir=run,
            require_run_summary=require_run_summary,
            timestamp_mode=timestamp_mode,
        )

        if result.status == "passed":
            console.print("[green]✓ Run promoted successfully[/green]")
            raise typer.Exit(0)
        else:
            console.print("[red]✗ Run promotion failed[/red]")
            raise typer.Exit(2)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@cli.command()
def commit_run(
    run: Path = typer.Option(
        ...,
        help="Path to run directory",
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
        help="Timestamp mode: deterministic or wallclock",
    ),
    no_repo_guard: bool = typer.Option(
        False,
        "--no-repo-guard",
        help="Skip TaskX repo detection (use with caution)",
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

    # Guard check
    _check_repo_guard(no_repo_guard)

    console.print("[cyan]Creating commit for run...[/cyan]")

    try:
        report = commit_run_impl(
            run_dir=run,
            message=message,
            allow_unpromoted=allow_unpromoted,
            timestamp_mode=timestamp_mode,
        )

        if report["status"] == "passed":
            console.print("[green]✓ Commit created successfully[/green]")
            console.print(f"[green]  Branch: {report['git']['branch']}[/green]")
            console.print(f"[green]  Commit: {report['git']['head_after']}[/green]")
            console.print(f"[green]  Files staged: {len(report['allowlist']['staged_files'])}[/green]")
            console.print(f"[green]  Report: {run / 'COMMIT_RUN.json'}[/green]")
            raise typer.Exit(0)
        else:
            console.print("[red]✗ Commit failed[/red]")
            for error in report.get("errors", []):
                console.print(f"[red]  • {error}[/red]")
            raise typer.Exit(2)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


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
        help="Timestamp mode: deterministic or wallclock",
    ),
) -> None:
    """Generate spec feedback from completed runs."""
    _require_module(generate_spec_feedback, "spec_feedback")

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
        raise typer.Exit(1)


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
        raise typer.Exit(1)


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

    # Detect Dopemux root and compute paths
    detection = detect_dopemux_root(override=dopemux_root)
    paths = compute_dopemux_paths(detection.root, out_root_override=out_root)

    console.print(f"[cyan]Dopemux root:[/cyan] {detection.root} ({detection.marker_used})")
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
        raise typer.Exit(1)


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

    # Detect Dopemux root and compute paths
    detection = detect_dopemux_root(override=dopemux_root)
    paths = compute_dopemux_paths(detection.root, out_root_override=out_root)

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
    
    packet_path = candidates[0]

    try:
        result = create_run_workspace(
            task_packet_path=packet_path,
            output_dir=paths.runs_out,
            run_id=run_id,
            timestamp_mode=timestamp_mode,
            pipeline_version=__version__,
        )
        console.print(f"[green]✓ Workspace created at: {result['run_dir']}[/green]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


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
        raise typer.Exit(1)


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
        raise typer.Exit(1)


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
        raise typer.Exit(1)


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
        raise typer.Exit(1)


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
        raise typer.Exit(1)


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
        raise typer.Exit(code=1)


@cli.command(name="ci-gate")
def ci_gate_cmd(
    out: Path = typer.Option(
        Path("./out/taskx_ci_gate"),
        "--out",
        "-o",
        help="Output directory for CI gate reports"
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
    run: Path | None = typer.Option(
        None,
        "--run",
        help="Specific run directory to validate promotion against"
    ),
    runs_root: Path | None = typer.Option(
        None,
        "--runs-root",
        help="Runs directory to search for latest run"
    ),
    promotion_filename: str = typer.Option(
        "PROMOTION.json",
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

    # Guard check
    _check_repo_guard(no_repo_guard)

    try:
        report = run_ci_gate(
            out_dir=out,
            timestamp_mode=timestamp_mode,
            require_git=require_git,
            run_dir=run,
            runs_root=runs_root,
            promotion_filename=promotion_filename,
            require_promotion=require_promotion,
            require_promotion_passed=require_promotion_passed
        )

        # Print summary
        typer.echo("\nTaskX CI Gate Report")
        typer.echo(f"Status: {report.status.upper()}")
        typer.echo(f"\nDoctor: {report.doctor['status']}")

        if report.promotion["required"]:
            promo_status = "✅ Validated" if report.promotion["validated"] else "❌ Failed"
            typer.echo(f"Promotion: {promo_status}")
            if report.promotion["run_dir"]:
                typer.echo(f"  Run: {report.promotion['run_dir']}")
        else:
            typer.echo("Promotion: Not required")

        typer.echo("\nChecks:")
        typer.echo(f"  Passed: {report.checks['passed']}")
        typer.echo(f"  Failed: {report.checks['failed']}")
        typer.echo(f"  Warnings: {report.checks['warnings']}")

        typer.echo("\nReports written to:")
        typer.echo(f"  {out / 'CI_GATE_REPORT.json'}")
        typer.echo(f"  {out / 'CI_GATE_REPORT.md'}")

        # Exit with appropriate code
        if report.status == "failed":
            typer.echo("\n❌ CI gate failed.")
            raise typer.Exit(code=2)
        else:
            typer.echo("\n✅ CI gate passed.")
            raise typer.Exit(code=0)

    except Exception as e:
        typer.echo(f"❌ CI gate run failed: {e}", err=True)
        raise typer.Exit(code=1)



# Bundle Commands

bundle_app = typer.Typer(
    name="bundle",
    help="Case bundle management commands",
    no_args_is_help=True,
)


def _require_exporter() -> None:
    if BundleExporter is None:
        console.print("[bold red]Error:[/bold red] BundleExporter not available")
        raise typer.Exit(1)


@bundle_app.command(name="export")
def bundle_export(
    last: int = typer.Option(10, help="Number of recent runs/packets to include"),
    out: Path = typer.Option(Path("./out/bundles"), help="Output directory for bundles"),
    case_id: str | None = typer.Option(None, help="Specific case ID (auto-generated if empty)"),
    config: Path | None = typer.Option(None, help="Path to bundle config yaml"),
) -> None:
    """Export a deterministic case bundle."""
    _require_exporter()

    console.print(f"[cyan]Exporting last {last} items...[/cyan]")

    try:
        # Detect repo root (naive: current dir)
        repo_root = Path.cwd()
        exporter = BundleExporter(repo_root=repo_root, config_path=config)
        exporter.export(last_n=last, out_dir=out, case_id=case_id)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Bundle export failed: {e}")
        raise typer.Exit(1)


cli.add_typer(bundle_app, name="bundle")


if __name__ == "__main__":

    cli()
