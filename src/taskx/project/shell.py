"""Repo-local shell wiring helpers for TaskX."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from taskx.project.common import read_template_text

REPORT_DIR = Path("out/taskx_project_shell")
REPORT_JSON = "PROJECT_SHELL_REPORT.json"
REPORT_MD = "PROJECT_SHELL_REPORT.md"


@dataclass(frozen=True)
class ShellFileSpec:
    """Managed shell wiring file spec."""

    relative_path: str
    template_name: str
    executable: bool


SHELL_FILES: tuple[ShellFileSpec, ...] = (
    ShellFileSpec(
        relative_path=".envrc",
        template_name="shell_envrc.template",
        executable=False,
    ),
    ShellFileSpec(
        relative_path="scripts/taskx",
        template_name="shell_taskx_shim.template",
        executable=True,
    ),
    ShellFileSpec(
        relative_path="scripts/taskx-local",
        template_name="shell_taskx_local.template",
        executable=True,
    ),
)


def init_shell(repo_root: Path) -> dict[str, Any]:
    """Create deterministic shell wiring files without overwriting existing files."""
    resolved_root = repo_root.resolve()
    resolved_root.mkdir(parents=True, exist_ok=True)

    created_files: list[str] = []
    skipped_files: list[str] = []
    file_states: list[dict[str, Any]] = []

    for spec in SHELL_FILES:
        target = resolved_root / spec.relative_path
        expected = read_template_text(spec.template_name)

        if target.exists():
            skipped_files.append(spec.relative_path)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(expected, encoding="utf-8")
            if spec.executable:
                target.chmod(0o755)
            created_files.append(spec.relative_path)

        file_states.append(_file_state(target, expected, spec))

    direnv_found = shutil.which("direnv") is not None
    next_steps = _next_steps(direnv_found)

    report = {
        "command": "init",
        "repo_root": str(resolved_root),
        "created_files": created_files,
        "skipped_files": skipped_files,
        "files": file_states,
        "direnv_found": direnv_found,
        "next_steps": next_steps,
    }
    report_paths = _write_report(resolved_root, report)
    report["report_paths"] = report_paths
    return report


def status_shell(repo_root: Path) -> dict[str, Any]:
    """Report shell wiring status and write project shell report files."""
    resolved_root = repo_root.resolve()

    created_files: list[str] = []
    skipped_files: list[str] = []
    file_states: list[dict[str, Any]] = []

    for spec in SHELL_FILES:
        target = resolved_root / spec.relative_path
        expected = read_template_text(spec.template_name)
        state = _file_state(target, expected, spec)
        file_states.append(state)
        if state["exists"]:
            skipped_files.append(spec.relative_path)

    direnv_found = shutil.which("direnv") is not None
    next_steps = _next_steps(direnv_found)

    report = {
        "command": "status",
        "repo_root": str(resolved_root),
        "created_files": created_files,
        "skipped_files": skipped_files,
        "files": file_states,
        "direnv_found": direnv_found,
        "next_steps": next_steps,
    }
    report_paths = _write_report(resolved_root, report)
    report["report_paths"] = report_paths
    return report


def _file_state(target: Path, expected: str, spec: ShellFileSpec) -> dict[str, Any]:
    exists = target.exists()
    content_matches = False
    executable_ok: bool | None = None

    if exists:
        actual = target.read_text(encoding="utf-8")
        content_matches = actual == expected
        if spec.executable:
            executable_ok = os.access(target, os.X_OK)

    valid = exists and content_matches and (True if executable_ok is None else executable_ok)

    return {
        "path": spec.relative_path,
        "exists": exists,
        "content_matches_template": content_matches,
        "executable_ok": executable_ok,
        "valid": valid,
    }


def _next_steps(direnv_found: bool) -> list[str]:
    if direnv_found:
        return [
            "Run: direnv allow",
            "Use scripts/taskx (or scripts/taskx-local) for repo-bound TaskX",
        ]

    return [
        "Install direnv (macOS): brew install direnv",
        'Enable shell hook (zsh): eval "$(direnv hook zsh)"',
        "Then run: direnv allow",
        "Use scripts/taskx (or scripts/taskx-local) for repo-bound TaskX",
    ]


def _write_report(repo_root: Path, report: dict[str, Any]) -> dict[str, str]:
    report_dir = repo_root / REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = report_dir / REPORT_JSON
    md_path = report_dir / REPORT_MD

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_markdown_report(report), encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
    }


def _render_markdown_report(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# PROJECT_SHELL_REPORT",
        "",
        f"- command: {report['command']}",
        f"- repo_root: {report['repo_root']}",
        f"- direnv_found: {report['direnv_found']}",
        "",
        "## Created Files",
        "",
    ]

    if report["created_files"]:
        lines.extend(f"- {path}" for path in report["created_files"])
    else:
        lines.append("- none")

    lines.extend(["", "## Skipped Files", ""])
    if report["skipped_files"]:
        lines.extend(f"- {path}" for path in report["skipped_files"])
    else:
        lines.append("- none")

    lines.extend(["", "## File Status", ""])
    for file_state in report["files"]:
        lines.append(f"### {file_state['path']}")
        lines.append(f"- exists: {file_state['exists']}")
        lines.append(f"- content_matches_template: {file_state['content_matches_template']}")
        if file_state["executable_ok"] is not None:
            lines.append(f"- executable_ok: {file_state['executable_ok']}")
        lines.append(f"- valid: {file_state['valid']}")
        lines.append("")

    lines.extend(["## Next Steps", ""])
    for step in report["next_steps"]:
        lines.append(f"- {step}")

    lines.append("")
    return "\n".join(lines)
