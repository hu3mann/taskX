import os
import yaml
import difflib
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from taskx.ops.compile import load_profile, compile_prompt, calculate_hash
from taskx.ops.discover import discover_instruction_file, get_sidecar_path
from taskx.ops.blocks import update_file, find_block, inject_block
from taskx.ops.doctor import run_doctor
from taskx.ops.manual import run_manual_mode

app = typer.Typer(help="Manage operator system instructions.")
console = Console()

def get_repo_root() -> Path:
    from taskx.utils.repo import detect_repo_root
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
    
    base_supervisor_text = """# BASE SUPERVISOR
- Task packets are law.
- Correctness over speed.
- Determinism is the goal.
"""
    lab_boundary_text = """# LAB BOUNDARY
- All tool outputs are simulated unless in PROD mode.
- Report all violations to the auditor.
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
    dry_run: bool = typer.Option(False, "--dry-run")
):
    """Apply compiled prompt to instruction files."""
    if dry_run:
        return preview(target, strategy)
        
    root = get_repo_root()
    profile = load_profile(root / "ops" / "operator_profile.yaml")
    templates_dir = root / "ops" / "templates"
    compiled = compile_prompt(profile, templates_dir)
    content_hash = calculate_hash(compiled)
    platform = profile.get("platform", {}).get("target", "chatgpt")
    model = profile.get("platform", {}).get("model", "UNKNOWN")

    target_file = target or discover_instruction_file(root) or get_sidecar_path(root)
    
    changed = update_file(target_file, compiled, platform, model, content_hash)
    if changed:
        console.print(f"[green]Updated {target_file}[/green]")
    else:
        console.print(f"[yellow]No changes needed for {target_file}[/yellow]")

@app.command()
def manual(
    out: Optional[Path] = typer.Option(None, "--out"),
    platform: Optional[str] = typer.Option(None, "--platform"),
    model: Optional[str] = typer.Option(None, "--model")
):
    """Run manual merge mode."""
    root = get_repo_root()
    profile = load_profile(root / "ops" / "operator_profile.yaml")
    templates_dir = root / "ops" / "templates"
    compiled = compile_prompt(profile, templates_dir, platform, model)
    
    run_manual_mode(compiled, platform or "chatgpt", model or "UNKNOWN")

@app.command()
def doctor(json: bool = typer.Option(False, "--json")):
    """Scan instruction files for issues and conflicts."""
    root = get_repo_root()
    report = run_doctor(root)
    
    if json:
        import json as json_lib
        print(json_lib.dumps(report, indent=2))
    else:
        console.print("[bold]TaskX Ops Doctor Report[/bold]")
        for f in report["files"]:
            if not f["exists"]:
                status = "[dim]MISSING[/dim]"
            elif f["has_block"]:
                status = "[green]OK[/green]"
            else:
                status = "[yellow]MISSING BLOCK[/yellow]"
                
            if f["duplicates"]:
                status = "[red]DUPLICATE BLOCKS[/red]"
            console.print(f"- {f['path']}: {status}")
            
        if report["conflicts"]:
            console.print("\n[red]Conflicts detected:[/red]")
            for c in report["conflicts"]:
                console.print(f"- {c['file']}:{c['line']}: {c['phrase']}")
                console.print(f"  [cyan]Rec:[/cyan] {c['recommendation']}")
