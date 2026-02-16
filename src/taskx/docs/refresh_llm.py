"""Deterministic LLM docs refresh with command surface and router summary."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml  # type: ignore[import-untyped]

from taskx.router.availability import AVAILABILITY_CONFIG_TEMPLATE, availability_path_for_repo

if TYPE_CHECKING:
    import typer

AUTOGEN_START = "<!-- TASKX:AUTOGEN:START -->"
AUTOGEN_END = "<!-- TASKX:AUTOGEN:END -->"
TARGET_FILES: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md", "CODEX.md")
REPORT_DIR = Path("out/taskx_docs_refresh_llm")
REPORT_JSON = "DOCS_REFRESH_LLM_REPORT.json"
REPORT_MD = "DOCS_REFRESH_LLM_REPORT.md"


@dataclass(frozen=True)
class CommandNode:
    """Tree node for deterministic command surface rendering."""

    name: str
    children: tuple[CommandNode, ...] = ()


class MarkerStructureError(RuntimeError):
    """Raised when autogen marker structure is invalid."""


def run_refresh_llm(*, repo_root: Path, cli_app: typer.Typer, check: bool = False) -> dict[str, Any]:
    """Run deterministic LLM docs refresh and return stable report payload."""
    resolved_repo = repo_root.resolve()
    tree = build_command_tree(cli_app)
    tree_lines = render_command_tree(tree)
    availability_summary = load_availability_summary(resolved_repo)
    block_text = render_autogen_block(tree_lines, availability_summary)
    block_hash = hashlib.sha256(block_text.encode("utf-8")).hexdigest()

    file_results: list[dict[str, Any]] = []
    created: list[str] = []
    modified: list[str] = []
    unchanged: list[str] = []
    refused: list[str] = []

    for filename in TARGET_FILES:
        path = resolved_repo / filename
        original = path.read_text(encoding="utf-8") if path.exists() else ""

        try:
            updated, markers_created, file_modified = inject_autogen(path, block_text, check=check)
            file_results.append(
                {
                    "path": filename,
                    "markers_created": markers_created,
                    "modified": file_modified,
                    "refusal_reason": None,
                }
            )

            if markers_created:
                created.append(filename)
            if file_modified:
                modified.append(filename)
            else:
                unchanged.append(filename)

            if not check and updated != original:
                path.write_text(updated, encoding="utf-8")
        except MarkerStructureError as exc:
            refused.append(filename)
            file_results.append(
                {
                    "path": filename,
                    "markers_created": False,
                    "modified": False,
                    "refusal_reason": str(exc),
                }
            )

    status = "ok"
    if refused:
        status = "refused"
    elif check and (created or modified):
        status = "drift"

    payload = {
        "status": status,
        "repo_root": str(resolved_repo),
        "check_mode": check,
        "files": sorted(file_results, key=lambda item: item["path"]),
        "availability_source": availability_summary["source"],
        "command_surface_hash": block_hash,
        "created": sorted(created),
        "modified": sorted(modified),
        "unchanged": sorted(unchanged),
        "refused": sorted(refused),
        "autogen_block": block_text,
    }

    write_refresh_report(repo_root=resolved_repo, report=payload)
    return payload


def build_command_tree(app: typer.Typer) -> CommandNode:
    """Build deterministic full-depth command tree from Typer registry."""
    children: list[CommandNode] = []

    command_names = sorted(_command_names(app))
    for name in command_names:
        children.append(CommandNode(name=name))

    group_map: dict[str, typer.Typer] = {}
    for group in app.registered_groups:
        if group.hidden:
            continue
        name = (group.name or "").strip()
        if name:
            group_map[name] = group.typer_instance  # type: ignore[assignment]

    for name in sorted(group_map):
        nested = build_command_tree(group_map[name])  # type: ignore[arg-type]
        children.append(CommandNode(name=name, children=nested.children))

    merged = _merge_nodes(children)
    return CommandNode(name="taskx", children=tuple(sorted(merged, key=lambda item: item.name)))


def render_command_tree(tree: CommandNode) -> list[str]:
    """Render deterministic full command tree as markdown bullet lines."""
    lines: list[str] = []

    def _walk(node: CommandNode, ancestors: tuple[str, ...], depth: int) -> None:
        path_tokens = ("taskx", *ancestors, node.name)
        indent = "  " * depth
        lines.append(f"{indent}- {' '.join(path_tokens)}")
        for child in sorted(node.children, key=lambda item: item.name):
            _walk(child, (*ancestors, node.name), depth + 1)

    for child in sorted(tree.children, key=lambda item: item.name):
        _walk(child, (), 0)

    return lines


def load_availability_summary(repo_root: Path) -> dict[str, Any]:
    """Load deterministic availability summary from repo config or defaults."""
    availability_path = availability_path_for_repo(repo_root)
    if availability_path.exists():
        source = "repo"
        payload = yaml.safe_load(availability_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError(f"Invalid availability file: {availability_path}")
    else:
        source = "default"
        payload = AVAILABILITY_CONFIG_TEMPLATE

    models_raw = payload.get("models", {})
    runners_raw = payload.get("runners", {})
    policy_raw = payload.get("policy", {})

    if not isinstance(models_raw, dict) or not isinstance(runners_raw, dict) or not isinstance(policy_raw, dict):
        raise RuntimeError("Invalid availability payload structure")

    available_models: list[str] = []
    for name in sorted(models_raw):
        entry = models_raw[name]
        if not isinstance(entry, dict):
            continue
        if entry.get("available", True):
            available_models.append(name)

    available_runners: list[str] = []
    for name in sorted(runners_raw):
        entry = runners_raw[name]
        if not isinstance(entry, dict):
            continue
        if bool(entry.get("available", False)):
            available_runners.append(name)

    ladder_value = policy_raw.get("escalation_ladder", [])
    if not isinstance(ladder_value, list):
        raise RuntimeError("Invalid availability policy escalation_ladder")

    ladder: list[str] = []
    for item in ladder_value:
        if isinstance(item, str) and item.strip():
            ladder.append(item.strip())

    snippet_model = available_models[0] if available_models else "example-model"
    snippet_runner = available_runners[0] if available_runners else "example-runner"
    snippet = [
        "models:",
        f"  {snippet_model}:",
        "    strengths: [cheap]",
        "    cost_tier: cheap",
        "    context: medium",
        "runners:",
        f"  {snippet_runner}:",
        "    available: true",
        "    strengths: [code_edit]",
        "policy:",
        f"  max_cost_tier: {policy_raw.get('max_cost_tier', 'high')}",
        f"  min_total_score: {policy_raw.get('min_total_score', 50)}",
        f"  stop_on_ambiguity: {policy_raw.get('stop_on_ambiguity', True)}",
        f"  escalation_ladder: [{', '.join(ladder)}]",
    ]

    return {
        "source": source,
        "available_runners": available_runners,
        "available_models": available_models,
        "policy": {
            "max_cost_tier": policy_raw.get("max_cost_tier", "high"),
            "min_total_score": policy_raw.get("min_total_score", 50),
            "stop_on_ambiguity": policy_raw.get("stop_on_ambiguity", True),
            "escalation_ladder": ladder,
        },
        "snippet": snippet,
    }


def render_autogen_block(tree_lines: list[str], availability_summary: dict[str, Any]) -> str:
    """Render deterministic autogen block text."""
    policy = availability_summary["policy"]
    lines: list[str] = [
        "## TaskX Command Surface (Autogenerated)",
        "",
        "### Command Tree",
        *tree_lines,
        "",
        "### Assisted Routing (taskx route)",
        "- Config: `.taskx/runtime/availability.yaml`",
        "- Artifacts:",
        "  - `out/taskx_route/ROUTE_PLAN.json`",
        "  - `out/taskx_route/ROUTE_PLAN.md`",
        "  - `out/taskx_route/HANDOFF.md`",
        "- Execution: assisted-only (prints handoffs; does not invoke external runners)",
        "",
        "### Availability Summary (deterministic)",
        f"- Available runners: {', '.join(availability_summary['available_runners'])}",
        f"- Available models: {', '.join(availability_summary['available_models'])}",
        "- Policy:",
        f"  - max_cost_tier: {policy['max_cost_tier']}",
        f"  - min_total_score: {policy['min_total_score']}",
        f"  - stop_on_ambiguity: {policy['stop_on_ambiguity']}",
        f"  - escalation_ladder: [{', '.join(policy['escalation_ladder'])}]",
        "",
        "### Minimal schema (snippet, stable)",
        "```yaml",
        *availability_summary["snippet"],
        "```",
        "",
        "Generated by: taskx docs refresh-llm",
    ]
    return "\n".join(lines)


def inject_autogen(path: Path, block_text: str, *, check: bool) -> tuple[str, bool, bool]:
    """Inject deterministic block into target file and return update metadata."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    marker_state = _validate_marker_structure(text)
    block = f"{AUTOGEN_START}\n{block_text}\n{AUTOGEN_END}"

    if marker_state == "missing":
        updated = _insert_block_after_title(text, block)
        return updated, True, updated != text

    start_index = text.find(AUTOGEN_START)
    end_index = text.find(AUTOGEN_END, start_index + len(AUTOGEN_START))
    assert start_index >= 0 and end_index >= 0
    end_index += len(AUTOGEN_END)

    updated = f"{text[:start_index]}{block}{text[end_index:]}"
    if check:
        return text, False, updated != text
    return updated, False, updated != text


def write_refresh_report(*, repo_root: Path, report: dict[str, Any]) -> None:
    """Write deterministic JSON and markdown refresh reports."""
    out_dir = repo_root / REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    json_report = {key: value for key, value in report.items() if key != "autogen_block"}
    (out_dir / REPORT_JSON).write_text(json.dumps(json_report, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# DOCS_REFRESH_LLM_REPORT",
        "",
        f"- status: {report['status']}",
        f"- check_mode: {report['check_mode']}",
        f"- availability_source: {report['availability_source']}",
        f"- command_surface_hash: {report['command_surface_hash']}",
        f"- created: {', '.join(report['created']) if report['created'] else 'none'}",
        f"- modified: {', '.join(report['modified']) if report['modified'] else 'none'}",
        f"- unchanged: {', '.join(report['unchanged']) if report['unchanged'] else 'none'}",
        f"- refused: {', '.join(report['refused']) if report['refused'] else 'none'}",
        "",
        "## File Results",
        "",
    ]

    for item in report["files"]:
        lines.append(f"- {item['path']}: modified={item['modified']}, markers_created={item['markers_created']}, refusal_reason={item['refusal_reason']}")

    lines.append("")
    (out_dir / REPORT_MD).write_text("\n".join(lines), encoding="utf-8")


def _insert_block_after_title(text: str, block: str) -> str:
    """Insert new marker block near file start, after H1 when present."""
    if not text.strip():
        return f"{block}\n"

    lines = text.splitlines(keepends=True)
    insert_at = len(lines)
    for index, line in enumerate(lines):
        if line.startswith("# "):
            insert_at = index + 1
            break

    prefix = "".join(lines[:insert_at])
    suffix = "".join(lines[insert_at:])

    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    prefix = prefix.rstrip("\n") + "\n\n"

    if suffix and not suffix.startswith("\n"):
        suffix = "\n" + suffix

    return f"{prefix}{block}{suffix}"


def _validate_marker_structure(text: str) -> str:
    """Validate marker structure and return 'missing' or 'valid'."""
    start_count = text.count(AUTOGEN_START)
    end_count = text.count(AUTOGEN_END)

    if start_count == 0 and end_count == 0:
        return "missing"

    if start_count != 1 or end_count != 1:
        raise MarkerStructureError("Invalid AUTOGEN marker structure")

    start_index = text.find(AUTOGEN_START)
    end_index = text.find(AUTOGEN_END)
    if start_index > end_index:
        raise MarkerStructureError("Invalid AUTOGEN marker structure")

    return "valid"


def _command_names(app: typer.Typer) -> set[str]:
    names: set[str] = set()
    for command in app.registered_commands:
        if command.hidden:
            continue
        callback = command.callback
        callback_name = getattr(callback, "__name__", "") if callback else ""
        name = command.name or callback_name.replace("_", "-")
        cleaned = name.strip()
        if cleaned:
            names.add(cleaned)
    return names


def _merge_nodes(nodes: list[CommandNode]) -> list[CommandNode]:
    merged: dict[str, CommandNode] = {}
    for node in nodes:
        existing = merged.get(node.name)
        if existing is None:
            merged[node.name] = node
            continue

        combined_children = [*existing.children, *node.children]
        merged[node.name] = CommandNode(name=node.name, children=tuple(_merge_nodes(combined_children)))

    return list(merged.values())
