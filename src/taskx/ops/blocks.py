import re
from pathlib import Path
from typing import NamedTuple

class BlockMatch(NamedTuple):
    start: int
    end: int
    platform: str
    model: str
    hash: str
    content: str

def find_block(text: str) -> BlockMatch | None:
    pattern = r"<!-- TASKX:BEGIN operator_system v=1 platform=(.*?) model=(.*?) hash=(.*?) -->\n(.*?)\n<!-- TASKX:END operator_system -->"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return BlockMatch(
            start=match.start(),
            end=match.end(),
            platform=match.group(1),
            model=match.group(2),
            hash=match.group(3),
            content=match.group(4)
        )
    return None

def inject_block(text: str, content: str, platform: str, model: str, content_hash: str) -> str:
    block = f"<!-- TASKX:BEGIN operator_system v=1 platform={platform} model={model} hash={content_hash} -->\n{content}\n<!-- TASKX:END operator_system -->"

    existing = find_block(text)
    if existing:
        return text[:existing.start] + block + text[existing.end:]

    if text.strip():
        return text.rstrip() + "\n\n" + block + "\n"
    return block + "\n"

def update_file(path: Path, content: str, platform: str, model: str, content_hash: str) -> bool:
    if path.exists():
        text = path.read_text()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = ""

    existing = find_block(text)
    if existing and existing.hash == content_hash:
        return False # No change

    new_text = inject_block(text, content, platform, model, content_hash)
    path.write_text(new_text)
    return True
