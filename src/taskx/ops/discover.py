from pathlib import Path

def discover_instruction_file(repo_root: Path) -> Path | None:
    candidates = [
        ".claude/CLAUDE.md",
        "CLAUDE.md",
        "claude.md",
        "AGENTS.md",
        "AI.md",
        "README_AI.md",
    ]
    for rel_path in candidates:
        full_path = repo_root / rel_path
        if full_path.exists():
            return full_path
    return None

def get_sidecar_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "llm" / "TASKX_OPERATOR_SYSTEM.md"
