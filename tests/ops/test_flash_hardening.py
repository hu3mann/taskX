import pytest
from pathlib import Path
from taskx.ops.cli import init, compile, apply, doctor
from taskx.ops.doctor import run_doctor
from taskx.ops.compile import calculate_hash
from typer.testing import CliRunner

def test_doctor_statuses_flash(tmp_path):
    # Mock get_repo_root
    import taskx.ops.cli
    original_get_repo_root = taskx.ops.cli.get_repo_root
    taskx.ops.cli.get_repo_root = lambda: tmp_path
    
    try:
        runner = CliRunner()
        
        # Setup: minimal repo structure
        ops_dir = tmp_path / "ops"
        ops_dir.mkdir()
        templates_dir = ops_dir / "templates"
        templates_dir.mkdir()
        (templates_dir / "overlays").mkdir()
        
        # 1. MISSING
        result = runner.invoke(taskx.ops.cli.app, ["doctor"])
        assert "CLAUDE.md: MISSING" in result.stdout
        
        # 2. NO_BLOCK
        (tmp_path / "CLAUDE.md").write_text("# No block here")
        result = runner.invoke(taskx.ops.cli.app, ["doctor"])
        assert "CLAUDE.md: NO_BLOCK" in result.stdout
        
        # 3. BLOCK_OK
        # We need a profile and compiled prompt
        (ops_dir / "operator_profile.yaml").write_text("project: {name: test, repo_root: '.', timezone: UTC}\ntaskx: {pin_type: git, pin_value: '123', cli_min_version: '0.1.0'}\nplatform: {target: chatgpt, model: flash}\n")
        (templates_dir / "base_supervisor.md").write_text("# BASE\n")
        (templates_dir / "lab_boundary.md").write_text("# LAB\n")
        (templates_dir / "overlays" / "chatgpt.md").write_text("# OPT\n")
        
        runner.invoke(taskx.ops.cli.app, ["compile"])
        compiled_path = ops_dir / "OUT_OPERATOR_SYSTEM_PROMPT.md"
        assert compiled_path.exists()
        compiled_content = compiled_path.read_text()
        compiled_hash = calculate_hash(compiled_content)
        
        runner.invoke(taskx.ops.cli.app, ["apply"])
        result = runner.invoke(taskx.ops.cli.app, ["doctor"])
        assert "CLAUDE.md: BLOCK_OK" in result.stdout
        assert f"compiled_hash={compiled_hash}" in result.stdout
        assert f"file_hash={compiled_hash}" in result.stdout
        assert "canonical_target=CLAUDE.md" in result.stdout
        
        # 4. BLOCK_STALE
        # Change a template without re-compiling/applying
        (templates_dir / "base_supervisor.md").write_text("# STALE\n")
        # compiled_hash should change if it re-compiles in doctor (it does if OUT... doesn't exist OR if we use the logic in doctor)
        # Wait, doctor.py uses OUT... if it exists.
        # If we didn't re-compile, OUT... still has the old content.
        # But wait, doctor.py:
        # if compiled_path.exists(): report["compiled_hash"] = calculate_hash(compiled_path.read_text())
        compiled_path.unlink()
        result = runner.invoke(taskx.ops.cli.app, ["doctor"])
        assert "CLAUDE.md: BLOCK_STALE" in result.stdout
        
        # 5. BLOCK_DUPLICATE
        # Add another block
        claude_content = (tmp_path / "CLAUDE.md").read_text()
        (tmp_path / "CLAUDE.md").write_text(claude_content + "\n" + claude_content)
        result = runner.invoke(taskx.ops.cli.app, ["doctor"])
        assert "CLAUDE.md: BLOCK_DUPLICATE" in result.stdout

    finally:
        taskx.ops.cli.get_repo_root = original_get_repo_root

def test_template_seed_no_overwrite(tmp_path):
    import taskx.ops.cli
    original_get_repo_root = taskx.ops.cli.get_repo_root
    taskx.ops.cli.get_repo_root = lambda: tmp_path
    
    try:
        runner = CliRunner()
        # Seed first time
        runner.invoke(taskx.ops.cli.app, ["init", "--yes"])
        base_p = tmp_path / "ops" / "templates" / "base_supervisor.md"
        assert "Canonical Minimal Baseline v1" in base_p.read_text()
        
        # Modify
        base_p.write_text("CUSTOM")
        # Seed second time
        runner.invoke(taskx.ops.cli.app, ["init", "--yes"])
        assert base_p.read_text() == "CUSTOM"
        
    finally:
        taskx.ops.cli.get_repo_root = original_get_repo_root
