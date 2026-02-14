from pathlib import Path

from taskx.ops.compile import compile_prompt, load_profile, calculate_hash
from taskx.ops.conflicts import check_conflicts

def extract_operator_blocks(text: str) -> list[str]:
    """
    Extract operator system blocks using a deterministic line-based scanner.
    
    Algorithm:
    1. Convert newlines: lines = text.splitlines()
    2. Iterate i=0..len(lines)-1
    3. When BEGIN line found:
        - set start = i+1
        - search forward for END line where lines[j].strip() == "<!-- TASKX:END operator_system -->"
        - if END not found: treat as zero blocks
        - else capture inner = "\n".join(lines[start:j])
        - append inner to blocks list
        - set i = j
    4. Return blocks list
    """
    lines = text.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "<!-- TASKX:BEGIN operator_system" in line:
            start = i + 1
            found_end = False
            for j in range(start, len(lines)):
                if lines[j].strip() == "<!-- TASKX:END operator_system -->":
                    inner = "\n".join(lines[start:j])
                    blocks.append(inner)
                    i = j
                    found_end = True
                    break
            if not found_end:
                # If END not found for one BEGIN, packet says treat as zero blocks.
                # However, practically it means we stop here and return what we found?
                # "if END not found: treat as zero blocks (do not crash)"
                return []
        i += 1
    return blocks

def get_canonical_target(repo_root: Path) -> Path:
    """
    Returns the canonical target for instruction blocks following the GOV policy:
    1. .claude/CLAUDE.md
    2. CLAUDE.md
    3. claude.md
    4. AGENTS.md
    5. fallback: docs/llm/TASKX_OPERATOR_SYSTEM.md
    """
    candidates = [
        ".claude/CLAUDE.md",
        "CLAUDE.md",
        "claude.md",
        "AGENTS.md"
    ]
    for rel in candidates:
        p = repo_root / rel
        if p.exists():
            return p
    return repo_root / "docs/llm/TASKX_OPERATOR_SYSTEM.md"

def run_doctor(repo_root: Path) -> dict:
    report = {
        "compiled_hash": "UNKNOWN",
        "canonical_target": str(get_canonical_target(repo_root).relative_to(repo_root)),
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
        blocks = extract_operator_blocks(text)
        
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
