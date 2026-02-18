import re
from pathlib import Path
from typing import List, NamedTuple

class Conflict(NamedTuple):
    path: Path
    phrase: str
    line: int
    recommendation: str

CONFLICT_PATTERNS = [
    (r"Always choose speed over correctness", "TaskX values correctness. Remove or qualify this instruction."),
    (r"You are the implementer", "TaskX defines the operator role as supervisor. Ensure role alignment."),
    (r"Ignore task packets", "Task packets are the source of truth for TaskX operations."),
]

def check_conflicts(path: Path) -> List[Conflict]:
    if not path.exists():
        return []
    
    conflicts = []
    text = path.read_text()
    lines = text.splitlines()
    
    for i, line in enumerate(lines, 1):
        for pattern, recommendation in CONFLICT_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                conflicts.append(Conflict(path, line.strip(), i, recommendation))
                
    return conflicts
