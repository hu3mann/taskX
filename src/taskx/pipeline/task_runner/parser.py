"""Task packet parser."""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING

from taskx.pipeline.task_runner.types import (
    CommitStep,
    ProjectIdentity,
    TaskPacketInfo,
)

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


def parse_task_packet(
    packet_path: Path,
    *,
    packet_required_header: bool = False,
) -> TaskPacketInfo:
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
    project_identity = _extract_project_identity(sections.get("PROJECT IDENTITY"))
    _assert_project_identity_header(
        project_identity=project_identity,
        packet_required_header=packet_required_header,
    )

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
    commit_plan = _extract_commit_plan(
        sections.get("COMMIT PLAN"),
        packet_path=packet_path,
    )

    return TaskPacketInfo(
        id=packet_id,
        title=title,
        path=str(packet_path),
        sha256=sha256,
        allowlist=allowlist,
        sources=sources,
        verification_commands=verification,
        commit_plan=commit_plan,
        sections=sections,
        project_identity=project_identity,
    )


def parse_packet_project_identity(
    packet_path: Path,
    *,
    packet_required_header: bool = False,
) -> ProjectIdentity | None:
    """Parse PROJECT IDENTITY section without validating full packet structure."""
    content = packet_path.read_text(encoding="utf-8")
    sections = _parse_sections(content)
    project_identity = _extract_project_identity(sections.get("PROJECT IDENTITY"))
    _assert_project_identity_header(
        project_identity=project_identity,
        packet_required_header=packet_required_header,
    )
    return project_identity


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


def _extract_project_identity(section_content: str | None) -> ProjectIdentity | None:
    """Parse optional PROJECT IDENTITY section key/value pairs."""
    if section_content is None:
        return None

    parsed: dict[str, str] = {}
    for raw_line in section_content.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("-") or line.startswith("*"):
            line = re.sub(r"^[-*]\s+", "", line).strip()
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key_norm = key.strip().lower().replace(" ", "_")
        value_norm = value.strip()
        if value_norm:
            parsed[key_norm] = value_norm

    project_id = parsed.get("project_id", "").strip()
    if not project_id:
        return None

    intended_repo = parsed.get("intended_repo")
    if intended_repo is not None:
        intended_repo = intended_repo.strip() or None

    return ProjectIdentity(
        project_id=project_id,
        intended_repo=intended_repo,
    )


def _assert_project_identity_header(
    *,
    project_identity: ProjectIdentity | None,
    packet_required_header: bool,
) -> None:
    if packet_required_header and project_identity is None:
        raise ValueError(
            "ERROR: Task Packet missing required PROJECT IDENTITY header.\n"
            "Refusing to run."
        )


def _extract_commit_plan(
    section_content: str | None,
    *,
    packet_path: Path,
) -> list[CommitStep] | None:
    """Extract optional commit plan from fenced JSON block."""
    if section_content is None:
        return None

    code_block_match = re.search(
        r"```(?:json)?\n(.*?)\n```",
        section_content,
        re.DOTALL,
    )
    if not code_block_match:
        raise ValueError(
            f"Task packet {packet_path} has COMMIT PLAN section without fenced JSON block"
        )

    raw_json = code_block_match.group(1).strip()
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Task packet {packet_path} has invalid COMMIT PLAN JSON: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Task packet {packet_path} COMMIT PLAN must be a JSON object")

    raw_plan = payload.get("commit_plan")
    if not isinstance(raw_plan, list):
        raise ValueError(
            f"Task packet {packet_path} COMMIT PLAN must define a non-empty 'commit_plan' list"
        )

    steps: list[CommitStep] = []
    for idx, raw_step in enumerate(raw_plan, start=1):
        if not isinstance(raw_step, dict):
            raise ValueError(
                f"Task packet {packet_path} COMMIT PLAN step {idx} must be an object"
            )

        step_id = raw_step.get("step_id")
        message = raw_step.get("message")
        allowlist = raw_step.get("allowlist")
        verify = raw_step.get("verify")

        if not isinstance(step_id, str) or not step_id.strip():
            raise ValueError(
                f"Task packet {packet_path} COMMIT PLAN step {idx} has empty step_id"
            )
        if not isinstance(message, str) or not message.strip():
            raise ValueError(
                f"Task packet {packet_path} COMMIT PLAN step {idx} has empty message"
            )
        if not isinstance(allowlist, list) or not allowlist:
            raise ValueError(
                f"Task packet {packet_path} COMMIT PLAN step {idx} has empty allowlist"
            )

        clean_allowlist: list[str] = []
        for allow_idx, item in enumerate(allowlist, start=1):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(
                    f"Task packet {packet_path} COMMIT PLAN step {idx} "
                    f"allowlist item {allow_idx} must be a non-empty string"
                )
            clean_allowlist.append(item.strip())

        verify_commands: list[str] | None = None
        if verify is not None:
            if not isinstance(verify, list):
                raise ValueError(
                    f"Task packet {packet_path} COMMIT PLAN step {idx} verify must be a list"
                )
            verify_commands = []
            for verify_idx, command in enumerate(verify, start=1):
                if not isinstance(command, str) or not command.strip():
                    raise ValueError(
                        f"Task packet {packet_path} COMMIT PLAN step {idx} "
                        f"verify command {verify_idx} must be a non-empty string"
                    )
                verify_commands.append(command.strip())

        steps.append(
            CommitStep(
                step_id=step_id.strip(),
                message=message.strip(),
                allowlist=clean_allowlist,
                verify=verify_commands,
            )
        )

    return steps
