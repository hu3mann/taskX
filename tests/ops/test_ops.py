import os
from pathlib import Path
import pytest
from taskx.ops.compile import calculate_hash, compile_prompt
from taskx.ops.blocks import inject_block, update_file, find_block
from taskx.ops.discover import discover_instruction_file
from taskx.ops.conflicts import check_conflicts

def test_idempotent_apply(tmp_path):
    target = tmp_path / "CLAUDE.md"
    target.write_text("# Existing content\n")
    
    content = "New operator instructions"
    c_hash = calculate_hash(content)
    platform = "chatgpt"
    model = "gpt-4"
    
    # First apply
    changed = update_file(target, content, platform, model, c_hash)
    assert changed is True
    first_bytes = target.read_bytes()
    
    # Second apply
    changed = update_file(target, content, platform, model, c_hash)
    assert changed is False
    second_bytes = target.read_bytes()
    
    assert first_bytes == second_bytes

def test_non_destructive_edit(tmp_path):
    target = tmp_path / "CLAUDE.md"
    original = "# Header\nUser content here.\n"
    target.write_text(original)
    
    content = "TaskX content"
    c_hash = calculate_hash(content)
    update_file(target, content, "chatgpt", "gpt-4", c_hash)
    
    updated_text = target.read_text()
    assert original in updated_text
    assert "<!-- TASKX:BEGIN operator_system" in updated_text

def test_replace_only_block(tmp_path):
    target = tmp_path / "CLAUDE.md"
    target.write_text("# Header\n<!-- TASKX:BEGIN operator_system v=1 platform=chatgpt model=gpt-4 hash=old -->\nOld content\n<!-- TASKX:END operator_system -->\nFooter")
    
    new_content = "New content"
    new_hash = calculate_hash(new_content)
    update_file(target, new_content, "chatgpt", "gpt-4", new_hash)
    
    updated_text = target.read_text()
    assert "# Header" in updated_text
    assert "Footer" in updated_text
    assert "New content" in updated_text
    assert "Old content" not in updated_text
    assert updated_text.count("<!-- TASKX:BEGIN") == 1

def test_discovery_order(tmp_path):
    # .claude/CLAUDE.md should win
    repo = tmp_path
    (repo / ".claude").mkdir()
    (repo / ".claude" / "CLAUDE.md").write_text("winner")
    (repo / "CLAUDE.md").write_text("loser")
    
    found = discover_instruction_file(repo)
    assert found.name == "CLAUDE.md"
    assert ".claude" in str(found)

def test_create_sidecar(tmp_path):
    # If no file exists, it should use get_sidecar_path logic
    from taskx.ops.discover import get_sidecar_path
    repo = tmp_path
    sidecar = get_sidecar_path(repo)
    
    content = "TaskX content"
    c_hash = calculate_hash(content)
    update_file(sidecar, content, "chatgpt", "gpt-4", c_hash)
    
    assert sidecar.exists()
    assert "TaskX content" in sidecar.read_text()

def test_conflict_detection(tmp_path):
    f = tmp_path / "CLAUDE.md"
    f.write_text("Always choose speed over correctness\nYou are the implementer")
    
    conflicts = check_conflicts(f)
    assert len(conflicts) == 2
    assert "correctness" in conflicts[0].phrase
    assert "implementer" in conflicts[1].phrase

def test_load_profile_missing(tmp_path):
    from taskx.ops.compile import load_profile
    assert load_profile(tmp_path / "missing.yaml") == {}

def test_doctor_full_lifecycle(tmp_path):
    from taskx.ops.doctor import run_doctor
    from taskx.ops.cli import init, compile, apply
    import os
    
    # 1. MISSING by default (candidates don't exist in tmp_path)
    repo = tmp_path
    report = run_doctor(repo)
    claude_info = next(f for f in report["files"] if f["path"] == "CLAUDE.md")
    assert claude_info["status"] == "MISSING"

    # 2. NO_BLOCK
    (repo / "CLAUDE.md").write_text("# Generic Info")
    report = run_doctor(repo)
    claude_info = next(f for f in report["files"] if f["path"] == "CLAUDE.md")
    assert claude_info["status"] == "NO_BLOCK"

    # Setup environment for init/compile (mocking git usually is enough if we don't care about real pin)
    # We'll use the profile to get a BLOCK_OK
    (repo / "ops").mkdir()
    (repo / "ops" / "templates").mkdir()
    (repo / "ops" / "templates" / "overlays").mkdir()
    (repo / "ops" / "templates" / "base_supervisor.md").write_text("# BASE\n")
    (repo / "ops" / "templates" / "lab_boundary.md").write_text("# LAB\n")
    (repo / "ops" / "templates" / "overlays" / "chatgpt.md").write_text("# OPT\n")
    
    profile_path = repo / "ops" / "operator_profile.yaml"
    profile_path.write_text("project: {name: test, repo_root: '.', timezone: UTC}\ntaskx: {pin_type: git, pin_value: '123', cli_min_version: '0.1.2'}\nplatform: {target: chatgpt, model: gpt-4}\n")

    # 3. BLOCK_OK
    # Need to simulate compile+apply logic
    from taskx.ops.compile import compile_prompt, load_profile, calculate_hash
    from taskx.ops.blocks import inject_block

    profile = load_profile(profile_path)
    compiled = compile_prompt(profile, repo / "ops" / "templates")
    chash = calculate_hash(compiled)
    
    injected = inject_block("# Header", compiled, "chatgpt", "gpt-4", chash)
    (repo / "CLAUDE.md").write_text(injected)
    
    report = run_doctor(repo)
    claude_info = next(f for f in report["files"] if f["path"] == "CLAUDE.md")
    assert report["compiled_hash"] == chash
    assert claude_info["file_hash"] == chash
    assert claude_info["status"] == "BLOCK_OK"

    # 4. BLOCK_STALE (change template)
    (repo / "ops" / "templates" / "base_supervisor.md").write_text("# CHANGED\n")
    report = run_doctor(repo)
    claude_info = next(f for f in report["files"] if f["path"] == "CLAUDE.md")
    assert claude_info["status"] == "BLOCK_STALE"
    assert claude_info["file_hash"] == chash
    assert report["compiled_hash"] != chash

    # 5. BLOCK_DUPLICATE
    (repo / "CLAUDE.md").write_text(injected + "\n" + injected)
    report = run_doctor(repo)
    claude_info = next(f for f in report["files"] if f["path"] == "CLAUDE.md")
    assert claude_info["status"] == "BLOCK_DUPLICATE"

def test_template_seeding_canonical(tmp_path):
    from taskx.ops.cli import init
    import os
    
    # Mock get_repo_root to return tmp_path
    import taskx.ops.cli
    original_get_repo_root = taskx.ops.cli.get_repo_root
    taskx.ops.cli.get_repo_root = lambda: tmp_path
    
    try:
        # Run init
        # Use a wrapper to avoid Typer dependency issues in tests if any
        from typer.testing import CliRunner
        from taskx.ops.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["init", "--yes"])
        
        base_p = tmp_path / "ops" / "templates" / "base_supervisor.md"
        assert "Canonical Minimal Baseline v1" in base_p.read_text()
        
        # Modify and re-run init (should not overwrite)
        base_p.write_text("USER EDITED")
        runner.invoke(app, ["init", "--yes"])
        assert base_p.read_text() == "USER EDITED"
        
    finally:
        taskx.ops.cli.get_repo_root = original_get_repo_root
