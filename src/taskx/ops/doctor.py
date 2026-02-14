from pathlib import Path
from typing import Dict, Any, List
from taskx.ops.discover import discover_instruction_file, get_sidecar_path
from taskx.ops.blocks import find_block
from taskx.ops.conflicts import check_conflicts, Conflict

def run_doctor(repo_root: Path) -> Dict[str, Any]:
    report = {
        "files": [],
        "conflicts": []
    }
    
    # Check common files
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
            "exists": path.exists(),
            "has_block": False,
            "hash_matches": False,
            "duplicates": False
        }
        
        if not path.exists():
            report["files"].append(file_info)
            continue
            
        text = path.read_text()
        blocks = re.findall(r"<!-- TASKX:BEGIN operator_system", text)
        if blocks:
            file_info["has_block"] = True
            if len(blocks) > 1:
                file_info["duplicates"] = True
        
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

import re
