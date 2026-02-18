import difflib
import subprocess
from pathlib import Path

import typer
import yaml  # type: ignore[import-untyped]
from rich.console import Console

from taskx import __version__
from taskx.ops.blocks import inject_block
from taskx.ops.discover import discover_instruction_file, get_sidecar_path
from taskx.ops.export import (
    calculate_hash,
    export_prompt,
    load_profile,
    write_if_changed,
)
from taskx.utils.repo import detect_repo_root

app = typer.Typer(help="Manage operator system instructions.")
console = Console()

def get_repo_root() -> Path:
    try:
        return detect_repo_root(Path.cwd()).root
    except RuntimeError:
        return Path.cwd()

def get_git_hash() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return "UNKNOWN"

def run_export_flow(
    export_path: Path | None = None,
    platform: str | None = None,
    model: str | None = None,
) -> bool:
    """Helper to run the export logic used by multiple commands."""
    root = get_repo_root()
    profile_path = root / "ops" / "operator_profile.yaml"
    profile = load_profile(profile_path)
    templates_dir = root / "ops" / "templates"

    git_hash = get_git_hash()

    compiled = export_prompt(
        profile,
        templates_dir,
        platform_override=platform,
        model_override=model,
        taskx_version=__version__,
        git_hash=git_hash
    )

    final_path = export_path or (root / "ops" / "EXPORTED_OPERATOR_PROMPT.md")
    changed = write_if_changed(final_path, compiled)

    console.print(f"Export: wrote {final_path} (changed={changed})")
    return changed

@app.command(hidden=True)
def compile(
    out_path: Path | None = typer.Option(None, "--out-path"),
    platform: str | None = typer.Option(None, "--platform"),
    model: str | None = typer.Option(None, "--model"),
) -> None:
    """Deprecated compatibility alias for `taskx ops export`."""
    console.print("[yellow]Deprecated:[/yellow] use `taskx ops export` instead of `taskx ops compile`.")
    run_export_flow(export_path=out_path, platform=platform, model=model)

@app.command()
def init(
    platform: str = typer.Option("chatgpt", "--platform"),
    model: str = typer.Option("gpt-5.2-thinking", "--model"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Non-interactive mode (accept defaults).",
    ),
    no_export: bool = typer.Option(False, "--no-export"),
    export_path: Path | None = typer.Option(None, "--export-path"),
):
    """Initialize TaskX operator configuration. Exports unified prompt by default."""
    root = get_repo_root()
    ops_dir = root / "ops"
    ops_dir.mkdir(exist_ok=True)

    profile_path = ops_dir / "operator_profile.yaml"
    if not profile_path.exists():
        profile = {
            "project": {
                "name": root.name,
                "repo_root": str(root),
                "timezone": "America/Vancouver"
            },
            "taskx": {
                "pin_type": "git_commit",
                "pin_value": get_git_hash(),
                "cli_min_version": __version__
            },
            "platform": {
                "target": platform,
                "model": model
            }
        }
        with open(profile_path, "w") as f:
            yaml.dump(profile, f)
        console.print(f"[green]Created {profile_path}[/green]")

    templates_dir = ops_dir / "templates"
    templates_dir.mkdir(exist_ok=True)
    (templates_dir / "overlays").mkdir(exist_ok=True)

    base_supervisor_text = """# BASE SUPERVISOR (Canonical Minimal Baseline v1)

## Role

You are the Supervisor / Auditor.

You:
- Author Task Packets.
- Enforce invariants.
- Audit implementer output.
- Protect determinism and auditability.

You are NOT:
- The implementer.
- A runtime generator.
- A copywriter.

## Authority Hierarchy (Highest -> Lowest)

1. Active Task Packet
2. Repository code and tests
3. Explicit schemas and formal contracts
4. Versioned project docs
5. Existing implementation
6. Model heuristics

If a conflict is detected:
- STOP.
- Surface the conflict explicitly.
- Do not auto-resolve.

## Non-Negotiables

- Task Packets are law.
- No fabrication.
- If evidence is missing -> mark UNKNOWN and request specific file/output.
- Prefer minimal diffs.
- Determinism over cleverness.
- Every change must be auditable.

## Determinism Contract

- Same inputs -> same outputs.
- No hidden randomness.
- No time-based logic unless explicitly allowed.
- Outputs must be reproducible.

## Output Discipline

Unless specified otherwise, responses must be one of:

- Design Spec
- Task Packet
- Patch Instructions
- Audit Report

Never mix formats.
"""
    lab_boundary_text = """# LAB BOUNDARY (Canonical Minimal Baseline v1)

## Project Context

You are operating inside a Development & Architecture Lab.

This lab:
- Designs systems.
- Defines prompts, rules, schemas, and invariants.
- Audits correctness and failure modes.

This lab does NOT:
- Act as live production runtime.
- Optimize for persuasion or conversion unless explicitly marked as test output.
- Generate final production artifacts unless instructed.

## Mode Discipline

If user intent is unclear:
- Ask for clarification.
- Do not guess.

If asked to perform runtime behavior inside lab mode:
- Pause and confirm whether this is lab testing or production generation.

## Correctness Priority

When forced to choose:
- Correctness over speed.
- Clarity over cleverness.
- Explicit contracts over implicit behavior.
"""

    # Seed canonical templates if missing
    for t, content in [("base_supervisor.md", base_supervisor_text), ("lab_boundary.md", lab_boundary_text)]:
        p = templates_dir / t
        if not p.exists():
            p.write_text(content)

    overlay_p = templates_dir / "overlays" / f"{platform}.md"
    if not overlay_p.exists():
        overlay_p.write_text(f"# {platform} Overlay\nSpecifics for {platform}\n")

    if not no_export:
        try:
            run_export_flow(export_path=export_path, platform=platform, model=model)
        except Exception:
            raise typer.Exit(1) from None

    console.print("[green]Initialization complete.[/green]")

@app.command()
def export(
    export_path: Path | None = typer.Option(None, "--export-path"),
    platform: str | None = typer.Option(None, "--platform"),
    model: str | None = typer.Option(None, "--model")
):
    """Export a unified operator system prompt from TaskX templates and profile configuration. Does not affect packet execution behavior."""
    run_export_flow(export_path=export_path, platform=platform, model=model)

@app.command()
def preview(
    target: Path | None = typer.Option(None, "--target")
):
    """Preview changes to instruction files."""
    root = get_repo_root()
    profile = load_profile(root / "ops" / "operator_profile.yaml")
    templates_dir = root / "ops" / "templates"
    compiled = export_prompt(profile, templates_dir, taskx_version=__version__, git_hash=get_git_hash())
    content_hash = calculate_hash(compiled)
    platform = profile.get("platform", {}).get("target", "chatgpt")
    model = profile.get("platform", {}).get("model", "UNKNOWN")

    target_file = target or discover_instruction_file(root) or get_sidecar_path(root)

    old_text = target_file.read_text() if target_file.exists() else ""

    new_text = inject_block(old_text, compiled, platform, model, content_hash)

    diff = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=str(target_file),
        tofile=str(target_file) + " (proposed)"
    )
    console.print("".join(diff))

@app.command()
def apply(
    target: Path | None = typer.Option(None, "--target"),
    strategy: str = typer.Option("append", "--strategy"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    platform: str | None = typer.Option(None, "--platform"),
    model: str | None = typer.Option(None, "--model")
):
    """Apply compiled prompt to instruction files."""
    from taskx.ops.doctor import get_canonical_target

    root = get_repo_root()
    profile = load_profile(root / "ops" / "operator_profile.yaml") or {}

    templates_dir = root / "ops" / "templates"

    # We must have content to apply. Prefer exported file, but export on the fly (in-memory) if missing.
    # Must NOT write export file.
    out_file_path = root / "ops" / "OUT_OPERATOR_SYSTEM_PROMPT.md"
    export_file_path = root / "ops" / "EXPORTED_OPERATOR_PROMPT.md"
    if out_file_path.exists():
        content = out_file_path.read_text()
    elif export_file_path.exists():
        content = export_file_path.read_text()
    else:
        try:
            content = export_prompt(profile, templates_dir, platform, model, taskx_version=__version__, git_hash=get_git_hash())
        except Exception as e:
            console.print(f"[red]Could not generate prompt: {e}[/red]")
            raise typer.Exit(1) from e

    content_hash = calculate_hash(content)

    # Target selection
    target_file = target or get_canonical_target(root)

    p = platform or profile.get("platform", {}).get("target", "chatgpt")
    m = model or profile.get("platform", {}).get("model", "UNKNOWN")

    # Write behavior rule: strategy == create-new and file exists -> sidecar
    if strategy == "create-new" and target_file.exists():
        from taskx.ops.discover import get_sidecar_path
        target_file = get_sidecar_path(root)

    old_text = target_file.read_text() if target_file.exists() else ""

    new_text = inject_block(old_text, content, p, m, content_hash)

    if old_text == new_text:
        console.print(f"No changes needed for {target_file}")
        return

    if dry_run:
        console.print(f"[yellow]Dry run: Proposed changes for {target_file}[/yellow]")
        diff = difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(target_file),
            tofile=str(target_file) + " (proposed)"
        )
        console.print("".join(diff))
        return

    # Write behavior
    if not target_file.exists():
        target_file.parent.mkdir(parents=True, exist_ok=True)

    target_file.write_text(new_text)
    console.print(f"[green]Updated {target_file}[/green]")

@app.command()
def manual(
    platform: str | None = typer.Option(None, "--platform"),
    model: str | None = typer.Option(None, "--model")
):
    """Run manual merge mode."""
    from taskx.ops.manual import run_manual_mode

    root = get_repo_root()
    profile = load_profile(root / "ops" / "operator_profile.yaml")
    compiled = export_prompt(profile, root / "ops" / "templates", taskx_version=__version__, git_hash=get_git_hash())
    run_manual_mode(compiled, platform or "chatgpt", model or "UNKNOWN")

@app.command()
def doctor(
    json: bool = typer.Option(False, "--json"),
    no_export: bool = typer.Option(False, "--no-export"),
    export_path: Path | None = typer.Option(None, "--export-path"),
):
    """Diagnose configuration drift and conflicts. Exports unified prompt by default."""
    from taskx.ops.doctor import run_doctor
    root = get_repo_root()
    report = run_doctor(root)

    if json:
        import json as json_lib
        print(json_lib.dumps(report, indent=2))
    else:
        print(f"compiled_hash={report['compiled_hash']}")
        print(f"canonical_target={report['canonical_target']}")
        print()

        config_locs = report.get("config_locations", {})
        if config_locs:
            print("Config locations:")
            for key, val in config_locs.items():
                print(f"  {key}={val or 'NOT_FOUND'}")
            print()

        for f in report["files"]:
            print(f"{f['path']}: {f['status']}")
            if f["status"] in ["BLOCK_OK", "BLOCK_STALE"]:
                print(f"file_hash={f['file_hash']}")
            print()

        if report["conflicts"]:
            print("Conflicts detected:")
            for c in report["conflicts"]:
                print(f"- {c['file']}:{c['line']}: {c['phrase']}")
                print(f"  Rec: {c['recommendation']}")

    # Export runs EVEN IF doctor status = FAIL
    # Logic note: report['files'] status determines FAIL if any FAIL-worthy status is present.
    # Current doctor doesn't explicitly return a "PASS/FAIL" summary status, but we'll assume it's based on file statuses.

    status_failed = any(f["status"] in ["BLOCK_STALE", "BLOCK_DUPLICATE", "NO_BLOCK"] for f in report["files"])

    if not no_export:
        run_export_flow(export_path=export_path)

    if status_failed:
        raise typer.Exit(2)

@app.command()
def diff():
    """Compare local configuration against last export."""
    # Placeholder for diff command if needed, though not explicitly requested in behavioral spec beyond listing it.
    pass

@app.command()
def handoff():
    """Execute handoff sequence."""
    pass
