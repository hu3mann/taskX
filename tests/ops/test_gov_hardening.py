import hashlib
from pathlib import Path
import pytest
from taskx.ops.doctor import extract_operator_blocks, run_doctor, get_canonical_target
from taskx.ops.cli import app
from typer.testing import CliRunner

runner = CliRunner()

def calculate_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def test_extract_operator_blocks_indented_end(tmp_path):
    # Match substring without colon
    content = "Line 1\r\n\r\n<!-- TASKX:BEGIN operator_system v=1 -->\r\n\r\nInner Content\r\n\r\n   <!-- TASKX:END operator_system -->\r\nLine 2"
    blocks = extract_operator_blocks(content)
    assert len(blocks) == 1
    expected_inner = "\nInner Content\n" 
    assert blocks[0] == expected_inner

def test_doctor_detects_duplicate_blocks_mixed_newlines(tmp_path):
    repo_root = tmp_path
    claude_md = repo_root / "CLAUDE.md"
    content = "<!-- TASKX:BEGIN operator_system -->\nBlock 1\n<!-- TASKX:END operator_system -->\r\n\r\n<!-- TASKX:BEGIN operator_system -->\r\nBlock 2\r\n   <!-- TASKX:END operator_system -->"
    claude_md.write_text(content)
    
    report = run_doctor(repo_root)
    file_info = next(f for f in report["files"] if f["path"] == "CLAUDE.md")
    assert file_info["status"] == "BLOCK_DUPLICATE"

def test_canonical_target_selection_order(tmp_path):
    repo_root = tmp_path
    # Priorities: .claude/CLAUDE.md > CLAUDE.md > AGENTS.md > fallback
    
    # 1. Fallback
    assert get_canonical_target(repo_root) == repo_root / "docs/llm/TASKX_OPERATOR_SYSTEM.md"
    
    # 2. AGENTS.md
    (repo_root / "AGENTS.md").write_text("Agents")
    assert get_canonical_target(repo_root) == repo_root / "AGENTS.md"
    
    # 3. CLAUDE.md
    (repo_root / "CLAUDE.md").write_text("CLAUDE")
    assert get_canonical_target(repo_root) == repo_root / "CLAUDE.md"
    
    # 4. .claude/CLAUDE.md
    (repo_root / ".claude").mkdir()
    (repo_root / ".claude/CLAUDE.md").write_text(".claude/CLAUDE")
    assert get_canonical_target(repo_root) == repo_root / ".claude/CLAUDE.md"

def test_apply_strategy_create_new_sidecar_fallback(tmp_path):
    repo_root = tmp_path
    (repo_root / ".git").mkdir()
    (repo_root / "CLAUDE.md").write_text("Original")
    
    ops_dir = repo_root / "ops"
    ops_dir.mkdir()
    (ops_dir / "operator_profile.yaml").write_text("project:\n  name: test\n")
    templates_dir = ops_dir / "templates"
    templates_dir.mkdir()
    (templates_dir / "base_supervisor.md").write_text("Base")
    (templates_dir / "lab_boundary.md").write_text("Lab")
    (templates_dir / "overlays").mkdir()
    (templates_dir / "overlays" / "chatgpt.md").write_text("Overlay")
    
    import os
    old_cwd = os.getcwd()
    os.chdir(repo_root)
    try:
        # If CLAUDE.md exists, strategy create-new should write to sidecar
        result = runner.invoke(app, ["apply", "--strategy", "create-new"])
        assert result.exit_code == 0
        assert (repo_root / "CLAUDE.md").read_text() == "Original"
        sidecar = repo_root / "docs/llm/TASKX_OPERATOR_SYSTEM.md"
        assert sidecar.exists()
    finally:
        os.chdir(old_cwd)

def test_apply_dry_run_no_write_v3(tmp_path):
    repo_root = tmp_path
    (repo_root / ".git").mkdir()
    sidecar = repo_root / "docs/llm/TASKX_OPERATOR_SYSTEM.md"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("Original")
    
    ops_dir = repo_root / "ops"
    ops_dir.mkdir()
    (ops_dir / "operator_profile.yaml").write_text("project:\n  name: test\n")
    templates_dir = ops_dir / "templates"
    templates_dir.mkdir()
    (templates_dir / "base_supervisor.md").write_text("Base")
    (templates_dir / "lab_boundary.md").write_text("Lab")
    (templates_dir / "overlays").mkdir()
    (templates_dir / "overlays" / "chatgpt.md").write_text("Overlay")
    
    import os
    old_cwd = os.getcwd()
    os.chdir(repo_root)
    try:
        result = runner.invoke(app, ["apply", "--dry-run"])
        assert result.exit_code == 0
        assert sidecar.read_text() == "Original"
    finally:
        os.chdir(old_cwd)
