import os
import yaml
import difflib
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from taskx.ops.compile import load_profile, compile_prompt, calculate_hash
from taskx.ops.discover import discover_instruction_file, get_sidecar_path
from taskx.utils.repo import detect_repo_root
from taskx.ops.blocks import inject_block, find_block

app = typer.Typer(help="Manage operator system instructions.")
console = Console()

def get_repo_root() -> Path:
    try:
        return detect_repo_root(Path.cwd()).root
    except RuntimeError:
        return Path.cwd()

@app.command()
def init(
    platform: str = typer.Option("chatgpt", "--platform"),
    model: str = typer.Option("gpt-5.2-thinking", "--model"),
    strategy: str = typer.Option("append", "--strategy"),
    yes: bool = typer.Option(False, "--yes")
):
    """Initialize operator profile and templates."""
    from taskx import __version__
    import subprocess
    
    root = get_repo_root()
    ops_dir = root / "ops"
    ops_dir.mkdir(exist_ok=True)
    
    # Try to get git head for pin
    pin_value = "UNKNOWN"
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        pin_value = out.decode().strip()
    except Exception:
        pass

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
                "pin_value": pin_value,
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

    for t, content in [("base_supervisor.md", base_supervisor_text), ("lab_boundary.md", lab_boundary_text)]:
        p = templates_dir / t
        if not p.exists():
            p.write_text(content)
            
    overlay_p = templates_dir / "overlays" / f"{platform}.md"
    if not overlay_p.exists():
        overlay_p.write_text(f"# {platform} Overlay\nSpecifics for {platform}\n")

    console.print("[green]Initialization complete.[/green]")

@app.command()
def compile(
    out: Optional[Path] = typer.Option(None, "--out"),
    platform: Optional[str] = typer.Option(None, "--platform"),
    model: Optional[str] = typer.Option(None, "--model")
):
    """Compile the operator system prompt."""
    root = get_repo_root()
    profile = load_profile(root / "ops" / "operator_profile.yaml")
    templates_dir = root / "ops" / "templates"
    
    compiled = compile_prompt(profile, templates_dir, platform, model)
    
    out_path = out or (root / "ops" / "OUT_OPERATOR_SYSTEM_PROMPT.md")
    out_path.write_text(compiled)
    console.print(f"[green]Compiled prompt written to {out_path}[/green]")

@app.command()
def preview(
    target: Optional[Path] = typer.Option(None, "--target"),
    strategy: str = typer.Option("append", "--strategy")
):
    """Preview changes to instruction files."""
    root = get_repo_root()
    profile = load_profile(root / "ops" / "operator_profile.yaml")
    templates_dir = root / "ops" / "templates"
    compiled = compile_prompt(profile, templates_dir)
    content_hash = calculate_hash(compiled)
    platform = profile.get("platform", {}).get("target", "chatgpt")
    model = profile.get("platform", {}).get("model", "UNKNOWN")

    target_file = target or discover_instruction_file(root) or get_sidecar_path(root)
    
    if target_file.exists():
        old_text = target_file.read_text()
    else:
        old_text = ""
        
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
    target: Optional[Path] = typer.Option(None, "--target"),
    strategy: str = typer.Option("append", "--strategy"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    platform: Optional[str] = typer.Option(None, "--platform"),
    model: Optional[str] = typer.Option(None, "--model")
):
    """Apply compiled prompt to instruction files."""
    from taskx.ops.compile import load_profile, calculate_hash, compile_prompt
    from taskx.ops.blocks import inject_block, find_block
    from taskx.ops.doctor import get_canonical_target
    import difflib
    
    root = get_repo_root()
    profile = load_profile(root / "ops" / "operator_profile.yaml") or {}
    
    templates_dir = root / "ops" / "templates"
    
    # We must have content to apply. Prefer compiled file, but compile on the fly if missing.
    compiled_path = root / "ops" / "OUT_OPERATOR_SYSTEM_PROMPT.md"
    if compiled_path.exists():
        content = compiled_path.read_text()
    else:
        try:
            content = compile_prompt(profile, templates_dir, platform, model)
        except Exception as e:
            console.print(f"[red]Could not compile prompt: {e}[/red]")
            raise typer.Exit(1)
            
    content_hash = calculate_hash(content)
    
    # Target selection
    if target:
        target_file = target
    else:
        # Canonical target selection policy
        target_file = get_canonical_target(root)
        
    p = platform or profile.get("platform", {}).get("target", "chatgpt")
    m = model or profile.get("platform", {}).get("model", "UNKNOWN")
    
    # Write behavior rule: strategy == create-new and file exists -> sidecar
    if strategy == "create-new" and target_file.exists():
        from taskx.ops.discover import get_sidecar_path
        target_file = get_sidecar_path(root)

    if target_file.exists():
        old_text = target_file.read_text()
    else:
        old_text = ""
        
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
    platform: Optional[str] = typer.Option(None, "--platform"),
    model: Optional[str] = typer.Option(None, "--model")
):
    """Run manual merge mode."""
    from taskx.ops.manual import run_manual_mode
    from taskx.ops.compile import compile_prompt, load_profile
    
    root = get_repo_root()
    profile = load_profile(root / "ops" / "operator_profile.yaml")
    compiled = compile_prompt(profile, root / "ops" / "templates")
    run_manual_mode(compiled, platform or "chatgpt", model or "UNKNOWN")

@app.command()
def doctor(
    json: bool = typer.Option(False, "--json")
):
    """Scan instruction files for issues and conflicts."""
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
        
        for f in report["files"]:
            print(f"{f['path']}: {f['status']}")
            if f["status"] in ["BLOCK_OK", "BLOCK_STALE"]:
                print(f"file_hash={f['file_hash']}")
            print()
