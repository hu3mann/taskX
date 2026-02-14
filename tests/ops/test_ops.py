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

def test_doctor_report(tmp_path):
    from taskx.ops.doctor import run_doctor
    repo = tmp_path
    (repo / "CLAUDE.md").write_text("# Test\n<!-- TASKX:BEGIN operator_system v=1 platform=chatgpt model=gpt-4 hash=abc -->\ncontent\n<!-- TASKX:END operator_system -->")
    
    report = run_doctor(repo)
    assert len(report["files"]) >= 1
    # Check CLAUDE.md exists and has block
    claude_info = next(f for f in report["files"] if f["path"] == "CLAUDE.md")
    assert claude_info["exists"] is True
    assert claude_info["has_block"] is True

    # Check non-existent file
    ai_info = next(f for f in report["files"] if f["path"] == "AI.md")
    assert ai_info["exists"] is False
    assert ai_info["has_block"] is False

def test_metadata_pin(tmp_path):
    # Mocking metadata is hard without full integration, 
    # but we can check if compile uses what's in profile.
    from taskx.ops.compile import compile_prompt
    profile = {
        "project": {"name": "test"},
        "taskx": {"pin_type": "git", "pin_value": "deadbeef", "cli_min_version": "0.1.2"},
        "platform": {"target": "chatgpt"}
    }
    prompt = compile_prompt(profile, tmp_path / "none")
    assert "deadbeef" in prompt
    assert "0.1.2" in prompt
