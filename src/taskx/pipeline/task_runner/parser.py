"""Task packet parser."""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from taskx.pipeline.task_runner.types import TaskPacketInfo

if TYPE_CHECKING:
    from pathlib import Path

REQUIRED_SECTIONS = [
    "GOAL",
    "SCOPE (ALLOWLIST)",
    "NON-NEGOTIABLES",
    "REQUIRED CHANGES",
    "VERIFICATION COMMANDS",
    "DEFINITION OF DONE",
    "SOURCES",
]


def parse_task_packet(packet_path: Path) -> TaskPacketInfo:
    """Parse a task packet markdown file.

    Args:
        packet_path: Path to task packet markdown file

    Returns:
        TaskPacketInfo with parsed data

    Raises:
        ValueError: If packet format is invalid
    """
    content = packet_path.read_text(encoding="utf-8")
    content_bytes = packet_path.read_bytes()

    # Compute hash
    sha256 = hashlib.sha256(content_bytes).hexdigest()

    # Extract ID and title from first H1
    first_line_match = re.match(
        r"^#\s+TASK_PACKET\s+(TP_\d{4})\s+—\s+(.+)$",
        content.split("\n")[0]
    )
    if not first_line_match:
        raise ValueError(
            f"Invalid task packet header in {packet_path}. "
            "Expected: # TASK_PACKET TP_#### — Title"
        )

    packet_id = first_line_match.group(1)
    title = first_line_match.group(2).strip()

    # Parse sections
    sections = _parse_sections(content)

    # Validate required sections
    missing = [sec for sec in REQUIRED_SECTIONS if sec not in sections]
    if missing:
        raise ValueError(
            f"Task packet {packet_path} missing required sections: {missing}"
        )

    # Extract allowlist
    allowlist = _extract_allowlist(sections["SCOPE (ALLOWLIST)"])
    if not allowlist:
        raise ValueError(
            f"Task packet {packet_path} has empty allowlist in SCOPE section"
        )

    # Extract verification commands
    verification = _extract_verification_commands(sections["VERIFICATION COMMANDS"])
    if not verification:
        raise ValueError(
            f"Task packet {packet_path} has no verification commands"
        )

    # Extract sources
    sources = _extract_sources(sections["SOURCES"])

    return TaskPacketInfo(
        id=packet_id,
        title=title,
        path=str(packet_path),
        sha256=sha256,
        allowlist=allowlist,
        sources=sources,
        verification_commands=verification,
        sections=sections,
    )


def _parse_sections(content: str) -> dict[str, str]:
    """Parse markdown sections by ## headings.

    Returns:
        Dict mapping section name to content
    """
    sections = {}
    current_section = None
    current_content: list[str] = []

    for line in content.split("\n"):
        # Check for H2 heading
        h2_match = re.match(r"^##\s+(.+)$", line)
        if h2_match:
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()

            # Start new section
            current_section = h2_match.group(1).strip()
            current_content = []
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def _extract_allowlist(section_content: str) -> list[str]:
    """Extract allowlist paths from SCOPE section.

    Parses markdown bullet list items that look like paths.
    """
    allowlist = []

    for line in section_content.split("\n"):
        line = line.strip()

        # Skip non-bullet lines and separators
        if not line.startswith("-") and not line.startswith("*"):
            continue

        # Remove bullet and whitespace
        item = re.sub(r"^[-*]\s+", "", line)

        # Remove backticks
        item = item.strip("`")
        item = item.strip()

        # Skip empty, non-path looking items, or markdown separators
        if not item or item.lower().startswith("only ") or item == "---" or all(c == "-" for c in item):
            continue

        allowlist.append(item)

    return allowlist


def _extract_verification_commands(section_content: str) -> list[str]:
    """Extract verification commands from section.

    Tries to extract from fenced code block first, then bullet list.
    """
    commands = []

    # Try fenced code block
    code_block_match = re.search(
        r"```(?:bash|sh)?\n(.*?)\n```",
        section_content,
        re.DOTALL
    )

    if code_block_match:
        code_content = code_block_match.group(1)
        for line in code_content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                commands.append(line)
    else:
        # Try bullet list
        for line in section_content.split("\n"):
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                item = re.sub(r"^[-*]\s+", "", line)
                item = item.strip("`")
                item = item.strip()
                if item:
                    commands.append(item)

    return commands


def _extract_sources(section_content: str) -> list[str]:
    """Extract source paths from SOURCES section."""
    sources = []

    for line in section_content.split("\n"):
        line = line.strip()

        # Look for backticked paths or bullet list items
        path_match = re.search(r"`([^`]+)`", line)
        if path_match:
            sources.append(path_match.group(1))
        elif line.startswith("-") or line.startswith("*"):
            item = re.sub(r"^[-*]\s+", "", line)
            # Extract path-like content
            item = item.strip("`")
            item = item.split(" ")[0]  # Take first word
            if item and "/" in item:
                sources.append(item)

    return sources
