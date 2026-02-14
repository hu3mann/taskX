import re
from pathlib import Path

from taskx.ops.compile import compile_prompt, load_profile, calculate_hash
from taskx.ops.conflicts import check_conflicts

def run_doctor(repo_root: Path) -> dict:
    report = {
        "compiled_hash": "UNKNOWN",
        "files": [],
        "conflicts": []
    }
    
    ops_dir = repo_root / "ops"
    templates_dir = ops_dir / "templates"
    profile_path = ops_dir / "operator_profile.yaml"
    compiled_path = ops_dir / "OUT_OPERATOR_SYSTEM_PROMPT.md"
    
    # Determine compiled_hash
    if compiled_path.exists():
        report["compiled_hash"] = calculate_hash(compiled_path.read_text())
    elif profile_path.exists():
        profile = load_profile(profile_path)
        try:
            compiled_prompt = compile_prompt(profile, templates_dir)
            report["compiled_hash"] = calculate_hash(compiled_prompt)
        except Exception:
            pass
    
    candidates = [
        ".claude/CLAUDE.md",
        "CLAUDE.md",
        "claude.md",
        "AGENTS.md",
        "AI.md",
        "README_AI.md",
        "docs/llm/TASKX_OPERATOR_SYSTEM.md"
    ]
    
    for rel_path in candidates:
        path = repo_root / rel_path
        file_info = {
            "path": rel_path,
            "status": "MISSING",
            "file_hash": None
        }
        
        if not path.exists():
            report["files"].append(file_info)
            continue
            
        text = path.read_text()
        # Find all operator_system blocks. 
        # Content is exactly between -->\n and \n<!--
        block_pattern = r"<!-- TASKX:BEGIN operator_system.*?-->\n(.*?)\n<!-- TASKX:END operator_system -->"
        blocks = re.findall(block_pattern, text, re.DOTALL)
        
        if not blocks:
            file_info["status"] = "NO_BLOCK"
        elif len(blocks) > 1:
            file_info["status"] = "BLOCK_DUPLICATE"
        else:
            # Exactly one block.
            inner_content = blocks[0]
            file_info["file_hash"] = calculate_hash(inner_content)
            
            if report["compiled_hash"] != "UNKNOWN" and file_info["file_hash"] == report["compiled_hash"]:
                file_info["status"] = "BLOCK_OK"
            else:
                file_info["status"] = "BLOCK_STALE"
        
        report["files"].append(file_info)
        
        conflicts = check_conflicts(path)
        for c in conflicts:
            report["conflicts"].append({
                "file": str(c.path.relative_to(repo_root)),
                "phrase": c.phrase,
                "line": c.line,
                "recommendation": c.recommendation
            })
            
    return report
