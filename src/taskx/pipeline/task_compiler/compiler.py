"""Core task packet compilation logic."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from taskx.pipeline.task_compiler.types import PacketSource, TaskPacket

if TYPE_CHECKING:
    from pathlib import Path


def _slugify(text: str) -> str:
    """Convert text to kebab-case slug."""
    # Lowercase, replace spaces/underscores with hyphens
    slug = text.lower()
    slug = re.sub(r"[_\s]+", "-", slug)
    # Remove non-alphanumeric except hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    return slug[:50]  # Max 50 chars


def _compute_input_hash(
    spec_sha256: str, source_index_sha256: str, mode: str, max_packets: int, seed: int
) -> str:
    """Compute deterministic input hash."""
    canonical = f"{spec_sha256}:{source_index_sha256}:{mode}:{max_packets}:{seed}"
    return hashlib.sha256(canonical.encode()).hexdigest()


def _parse_spec_requirements(spec_content: str) -> list[dict]:
    """Extract requirements from MASTER_DESIGN_SPEC markdown.

    Returns:
        List of dicts with {topic, text, source_path, line_no}
    """
    requirements = []
    lines = spec_content.split("\n")

    current_topic = "General"
    in_requirements_section = False

    for i, line in enumerate(lines, start=1):
        # Check for "Extracted Requirements" section
        if "## Extracted Requirements" in line:
            in_requirements_section = True
            continue

        if not in_requirements_section:
            continue

        # Check for topic headers (###)
        if line.startswith("### "):
            current_topic = line[4:].strip()
            continue

        # Extract requirement bullets with source
        if line.strip().startswith("- ") and not line.strip().startswith("- Source:"):
            req_text = line.strip()[2:].strip()

            # Look ahead for source line
            source_path = None
            source_line_no = None

            if i < len(lines):
                next_line = lines[i].strip()  # Next line (i+1 in 0-indexed)
                if next_line.startswith("- Source:"):
                    # Extract source: `path:line_no`
                    source_match = re.search(r"`([^`]+):(\d+)`", next_line)
                    if source_match:
                        source_path = source_match.group(1)
                        source_line_no = int(source_match.group(2))

            if req_text and source_path:
                requirements.append({
                    "topic": current_topic,
                    "text": req_text,
                    "source_path": source_path,
                    "line_no": source_line_no,
                })

    return requirements


def _categorize_requirement(req: dict, mode: str) -> str | None:
    """Categorize requirement into packet category.

    Returns:
        Category name or None if not relevant for mode.
    """
    text_lower = req["text"].lower()
    req["topic"].lower()

    # Heuristic mapping
    categories = []

    # Schema/validation/quarantine → Hardening
    if any(kw in text_lower for kw in ["schema", "validate", "quarantine", "strict"]):
        categories.append("hardening")

    # Cloud/synthesis → MVP (if foundational) or Hardening
    if any(kw in text_lower for kw in ["cloud", "synthesis", "citations", "responses"]):
        # If it's a "must" statement, likely MVP
        if "must" in text_lower:
            categories.append("mvp")
        else:
            categories.append("hardening")

    # Graph → MVP
    if any(kw in text_lower for kw in ["graph", "kuzu", "neo4j"]):
        categories.append("mvp")

    # Tests/determinism → Hardening
    if any(kw in text_lower for kw in ["test", "determinism", "offline"]):
        categories.append("hardening")

    # Filter by mode
    if mode == "mvp":
        return "mvp" if "mvp" in categories else None
    elif mode == "hardening":
        return "hardening" if "hardening" in categories else None
    elif mode == "full":
        return categories[0] if categories else None

    return None


def _group_requirements_into_packets(
    requirements: list[dict], mode: str, max_packets: int
) -> list[dict]:
    """Group requirements into logical task packets.

    Returns:
        List of packet dicts with {title, category, requirements}
    """
    # Categorize requirements
    categorized = {}

    for req in requirements:
        category = _categorize_requirement(req, mode)
        if category:
            topic = req["topic"]
            key = f"{category}:{topic}"

            if key not in categorized:
                categorized[key] = {
                    "category": category,
                    "topic": topic,
                    "requirements": [],
                }

            categorized[key]["requirements"].append(req)

    # Convert to packets (limit to max_packets)
    packet_groups = list(categorized.values())

    # Sort by category (mvp first), then topic
    packet_groups.sort(key=lambda g: (g["category"] != "mvp", g["topic"]))

    return packet_groups[:max_packets]


def _build_packet_from_group(
    group: dict, packet_id: str, source_index_files: set[str]
) -> TaskPacket:
    """Build a TaskPacket from a requirement group.

    Args:
        group: Dict with category, topic, requirements
        packet_id: Packet ID (e.g., TP_0001)
        source_index_files: Set of valid source paths

    Returns:
        TaskPacket instance
    """
    topic = group["topic"]
    category = group["category"]
    requirements = group["requirements"]

    # Build title
    title = f"Implement {topic}"
    slug = _slugify(title)

    # Extract goals
    goals = [req["text"] for req in requirements[:3]]  # Top 3

    # Extract sources (only valid ones)
    sources = []
    seen_paths = set()

    for req in requirements:
        path = req["source_path"]
        if path in source_index_files and path not in seen_paths:
            sources.append(PacketSource(path=path, heading_text=topic))
            seen_paths.add(path)

    # Infer allowlist (conservative)
    allowlist = []

    # Check if related to schemas
    if "schema" in topic.lower() or any("schema" in req["text"].lower() for req in requirements):
        # Find specific schema if mentioned
        for req in requirements:
            schema_match = re.search(r"(\w+)\.schema\.json", req["text"])
            if schema_match:
                allowlist.append(f"schemas/{schema_match.group(0)}")

        if not allowlist:
            allowlist.append("schemas/*.schema.json")

    # Check if related to CLI
    if "cli" in topic.lower() or "command" in topic.lower():
        allowlist.append("src/chatx/cli/main.py")

    # Check if related to specific modules
    if "synthesis" in topic.lower():
        allowlist.append("src/chatx/synthesis/*.py")
        allowlist.append("tests/unit/synthesis/*.py")

    if "graph" in topic.lower() or "kuzu" in topic.lower():
        allowlist.append("src/chatx/storage/*.py")
        allowlist.append("tests/unit/storage/*.py")

    # Default fallback
    if not allowlist:
        allowlist.append("src/chatx/**/*.py")
        allowlist.append("tests/**/*.py")

    # Set priority based on category
    priority = 1 if category == "mvp" else 3

    # Set effort (heuristic: based on number of requirements)
    effort = "S" if len(requirements) <= 2 else ("M" if len(requirements) <= 5 else "L")

    # Set risk
    risk = "med"  # Default
    if "cloud" in topic.lower() or "synthesis" in topic.lower():
        risk = "high"
    elif "test" in topic.lower():
        risk = "low"

    # Verification commands
    verification = [
        "python -m pytest -q tests/unit/",
    ]

    # Outputs (generic)
    outputs = []
    if "schema" in topic.lower():
        outputs.append("schemas/*.schema.json")

    # Notes
    notes = f"Auto-generated from {len(requirements)} requirement(s) in {topic}."

    return TaskPacket(
        id=packet_id,
        slug=slug,
        title=title,
        priority=priority,
        effort=effort,
        risk=risk,
        depends_on=[],  # Dependencies computed later
        allowlist=allowlist,
        sources=sources,
        goals=goals,
        verification=verification,
        outputs=outputs,
        notes=notes,
    )


def _compute_dependencies(packets: list[TaskPacket]) -> None:
    """Compute packet dependencies (mutates packets in place).

    Simple rule: schema packets must come before packets that use those schemas.
    """
    # Find schema packets
    schema_packet_ids = []
    for packet in packets:
        if any("schema" in allow for allow in packet.allowlist):
            schema_packet_ids.append(packet.id)

    # For each non-schema packet, depend on all schema packets
    for packet in packets:
        if packet.id not in schema_packet_ids:
            # Check if this packet might use schemas
            uses_schemas = any(
                "validate" in goal.lower() or "schema" in goal.lower()
                for goal in packet.goals
            )

            if uses_schemas:
                packet.depends_on = schema_packet_ids.copy()


def _write_packet_markdown(packet: TaskPacket, output_path: Path) -> None:
    """Write task packet as markdown file.

    Args:
        packet: TaskPacket to write
        output_path: File path for markdown
    """
    lines = [
        f"# TASK_PACKET {packet.id} — {packet.title}",
        "",
        "## GOAL",
        "",
        *[f"- {goal}" for goal in packet.goals],
        "",
        "---",
        "",
        "## SCOPE (ALLOWLIST)",
        "",
        "Only edit/create these files:",
        "",
        *[f"- `{allow}`" for allow in packet.allowlist],
        "",
        "---",
        "",
        "## NON-NEGOTIABLES",
        "",
        "- Task packets are law.",
        "- All changes must be deterministic and reproducible.",
        "- All JSON artifacts must validate strictly against schemas.",
        "- No network calls in tests.",
        "",
        "---",
        "",
        "## REQUIRED CHANGES",
        "",
        "(Implementation details to be determined based on goals above.)",
        "",
        "---",
        "",
        "## VERIFICATION COMMANDS",
        "",
        "```bash",
        *packet.verification,
        "```",
        "",
        "---",
        "",
        "## DEFINITION OF DONE",
        "",
        "- All goals achieved",
        "- Tests pass",
        "- Only allowlisted files changed",
        *[f"- Output artifact exists: `{output}`" for output in packet.outputs],
        "",
        "---",
        "",
        "## SOURCES",
        "",
        "This packet is based on requirements from:",
        "",
        *[f"- `{source.path}`" + (f" ({source.heading_text})" if source.heading_text else "") for source in packet.sources],
        "",
        "---",
        "",
        f"**Priority**: {packet.priority}/5 | **Effort**: {packet.effort} | **Risk**: {packet.risk}",
        "",
        f"**Notes**: {packet.notes}",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")


def compile_task_queue(
    *,
    spec_path: Path,
    source_index_path: Path,
    output_dir: Path,
    mode: str,
    max_packets: int,
    seed: int,
    pipeline_version: str,
    timestamp_mode: str = "deterministic",
) -> dict[str, Any]:
    """Compile task packets from mined spec.

    Args:
        spec_path: Path to MASTER_DESIGN_SPEC_V3.md
        source_index_path: Path to SOURCE_INDEX.json
        output_dir: Output directory for queue and packets
        mode: Compilation mode (mvp|hardening|full)
        max_packets: Maximum number of packets to generate
        seed: Seed value (for reproducibility)
        pipeline_version: Pipeline version string
        timestamp_mode: Timestamp mode - "deterministic" or "wallclock"

    Returns:
        Dict with paths to generated artifacts
    """
    # Read inputs
    spec_content = spec_path.read_text(encoding="utf-8")

    with source_index_path.open() as f:
        source_index = json.load(f)

    # Get valid source paths
    source_files = {file_info["path"] for file_info in source_index["files"]}

    # Compute input hashes
    spec_sha256 = hashlib.sha256(spec_content.encode()).hexdigest()
    source_index_sha256 = source_index["aggregate"]["corpus_hash"]

    input_hash = _compute_input_hash(
        spec_sha256, source_index_sha256, mode, max_packets, seed
    )

    # Parse requirements from spec
    requirements = _parse_spec_requirements(spec_content)

    # Group into packets
    packet_groups = _group_requirements_into_packets(requirements, mode, max_packets)

    # Build TaskPacket objects
    packets = []
    for i, group in enumerate(packet_groups, start=1):
        packet_id = f"TP_{i:04d}"
        packet = _build_packet_from_group(group, packet_id, source_files)
        packets.append(packet)

    # Compute dependencies
    _compute_dependencies(packets)

    # Sort by priority, then title
    packets.sort(key=lambda p: (p.priority, p.title))

    # Reassign IDs after sorting
    for i, packet in enumerate(packets, start=1):
        packet.id = f"TP_{i:04d}"

    # Determine timestamp
    if timestamp_mode == "deterministic":
        generated_at = "1970-01-01T00:00:00Z"
    elif timestamp_mode == "wallclock":
        generated_at = datetime.now(UTC).isoformat()
    else:
        raise ValueError(f"Invalid timestamp_mode: {timestamp_mode}")

    # Build queue dict
    queue_dict = {
        "schema_version": "1.0",
        "pipeline_version": pipeline_version,
        "generated_at": generated_at,
        "inputs": {
            "spec_path": str(spec_path),
            "source_index_path": str(source_index_path),
            "mode": mode,
            "max_packets": max_packets,
            "seed": seed,
            "input_hash": input_hash,
        },
        "packets": [
            {
                "id": p.id,
                "slug": p.slug,
                "title": p.title,
                "priority": p.priority,
                "effort": p.effort,
                "risk": p.risk,
                "depends_on": p.depends_on,
                "allowlist": p.allowlist,
                "sources": [
                    {"path": s.path, "heading_text": s.heading_text}
                    if s.heading_text
                    else {"path": s.path}
                    for s in p.sources
                ],
                "goals": p.goals,
                "verification": p.verification,
                "outputs": p.outputs,
                "notes": p.notes,
            }
            for p in packets
        ],
    }

    # Write outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write TASK_QUEUE.json
    from taskx.utils.json_output import write_json_strict

    queue_path = output_dir / "TASK_QUEUE.json"
    write_json_strict(
        data=queue_dict,
        output_path=queue_path,
        schema_name="task_queue",
        run_id=None,
        quarantine_dir=output_dir / "quarantine",
    )

    # Write packet markdown files
    packets_dir = output_dir / "TASK_PACKETS"
    packets_dir.mkdir(parents=True, exist_ok=True)

    for packet in packets:
        packet_filename = f"{packet.id}_{packet.slug}.md"
        packet_path = packets_dir / packet_filename
        _write_packet_markdown(packet, packet_path)

    return {
        "task_queue": str(queue_path),
        "packet_count": len(packets),
        "packets_dir": str(packets_dir),
    }
