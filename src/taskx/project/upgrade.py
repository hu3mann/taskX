"""Deterministic project upgrade orchestrator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from taskx.doctor import DoctorReport, run_doctor
from taskx.guard.identity import load_repo_identity
from taskx.project.doctor import fix_project, write_doctor_reports
from taskx.project.mode import normalize_mode
from taskx.project.shell import init_shell

UPGRADE_REPORT_DIR = Path("out/taskx_project_upgrade")
UPGRADE_REPORT_JSON = "PROJECT_UPGRADE_REPORT.json"
UPGRADE_REPORT_MD = "PROJECT_UPGRADE_REPORT.md"


class ProjectUpgradeRefusalError(RuntimeError):
    """Raised when preconditions block upgrade execution."""


def run_project_upgrade(
    repo_root: Path,
    instructions_path: Path,
    mode: str,
    *,
    shell: bool,
    packs: bool,
    doctor: bool,
    allow_init_rails: bool,
) -> dict[str, Any]:
    """Run deterministic project upgrade sequence and write report artifacts."""
    resolved_repo_root = repo_root.resolve()
    resolved_repo_root.mkdir(parents=True, exist_ok=True)

    resolved_instructions = _resolve_instructions_path(resolved_repo_root, instructions_path)
    normalized_mode = normalize_mode(mode)

    snapshot_targets = _snapshot_targets(resolved_repo_root, resolved_instructions)
    before_snapshot = snapshot_paths(resolved_repo_root, snapshot_targets)

    rails_state = ensure_rails(resolved_repo_root, allow_init_rails=allow_init_rails)

    shell_result: dict[str, Any] | None = None
    if shell:
        shell_result = init_shell(resolved_repo_root)

    packs_result: dict[str, Any] | None = None
    if packs:
        packs_report = fix_project(resolved_instructions, normalized_mode)
        packs_report_paths = write_doctor_reports(resolved_instructions, packs_report)
        packs_result = {
            "status": packs_report["status"],
            "applied_mode": packs_report.get("applied_mode", normalized_mode),
            "detected_mode": packs_report.get("detected_mode"),
            "actions_taken": packs_report.get("actions_taken", []),
            "checks": packs_report.get("checks", []),
            "report_paths": packs_report_paths,
        }

    doctor_result: dict[str, Any] | None = None
    if doctor:
        doctor_out = resolved_repo_root / "out" / "taskx_doctor"
        doctor_report = run_doctor(
            out_dir=doctor_out,
            timestamp_mode="deterministic",
            require_git=False,
            repo_root=resolved_repo_root,
        )
        doctor_result = _doctor_summary(doctor_report, doctor_out)

    after_snapshot = snapshot_paths(resolved_repo_root, snapshot_targets)
    change_summary = compute_change_summary(before_snapshot, after_snapshot)

    report = {
        "repo_root": str(resolved_repo_root),
        "instructions_path": str(resolved_instructions),
        "mode": normalized_mode,
        "options": {
            "shell": shell,
            "packs": packs,
            "doctor": doctor,
            "allow_init_rails": allow_init_rails,
        },
        "rails_state": rails_state,
        "shell_init": shell_result,
        "packs_doctor": packs_result,
        "doctor": doctor_result,
        "file_changes": change_summary,
    }
    report_paths = _write_upgrade_report(resolved_repo_root, report)
    report["report_paths"] = report_paths
    return report


def ensure_rails(repo_root: Path, *, allow_init_rails: bool) -> dict[str, Any]:
    """Ensure .taskxroot and .taskx/project.json exist (optionally initialize)."""
    taskxroot_path = repo_root / ".taskxroot"
    project_identity_path = repo_root / ".taskx" / "project.json"

    taskxroot_present_before = taskxroot_path.exists()
    project_identity_present_before = project_identity_path.exists()

    missing: list[str] = []
    if not taskxroot_present_before:
        missing.append(".taskxroot")
    if not project_identity_present_before:
        missing.append(".taskx/project.json")

    created: list[str] = []
    auto_derived_project_id = False

    if missing and not allow_init_rails:
        missing_list = ", ".join(missing)
        raise ProjectUpgradeRefusalError(
            f"ERROR: Missing identity rails ({missing_list}). Refusing to run. "
            "Re-run with --allow-init-rails to initialize rails."
        )

    if not taskxroot_present_before:
        taskxroot_path.touch(exist_ok=True)
        created.append(".taskxroot")

    if not project_identity_present_before:
        project_identity_path.parent.mkdir(parents=True, exist_ok=True)
        default_project_id = repo_root.name
        payload = {
            "project_id": default_project_id,
            "project_slug": default_project_id,
            "repo_remote_hint": default_project_id,
            "packet_required_header": True,
        }
        project_identity_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        created.append(".taskx/project.json")
        auto_derived_project_id = True

    try:
        identity = load_repo_identity(repo_root)
    except Exception as exc:  # pragma: no cover - exercised via refusal path
        raise ProjectUpgradeRefusalError(f"ERROR: Invalid identity rails: {exc}") from exc

    return {
        "taskxroot_present_before": taskxroot_present_before,
        "project_identity_present_before": project_identity_present_before,
        "missing_before": missing,
        "created": created,
        "allow_init_rails": allow_init_rails,
        "project_id": identity.project_id,
        "project_slug": identity.project_slug,
        "repo_remote_hint": identity.repo_remote_hint,
        "packet_required_header": identity.packet_required_header,
        "project_id_auto_derived": auto_derived_project_id,
        "status": "initialized" if created else "present",
    }


def snapshot_paths(repo_root: Path, paths: list[Path]) -> dict[str, str]:
    """Create deterministic hash snapshot for existing files inside target paths."""
    snapshot: dict[str, str] = {}
    for target in paths:
        if not target.exists():
            continue
        if target.is_file():
            rel = str(target.relative_to(repo_root))
            snapshot[rel] = _hash_file(target)
            continue
        for file_path in sorted(path for path in target.rglob("*") if path.is_file()):
            rel = str(file_path.relative_to(repo_root))
            snapshot[rel] = _hash_file(file_path)
    return snapshot


def compute_change_summary(before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    """Compute deterministic created/modified/deleted summary from snapshots."""
    before_keys = set(before)
    after_keys = set(after)

    created = sorted(after_keys - before_keys)
    deleted = sorted(before_keys - after_keys)
    modified = sorted(key for key in (before_keys & after_keys) if before[key] != after[key])

    return {
        "created": created,
        "modified": modified,
        "deleted": deleted,
        "changed_count": len(created) + len(modified) + len(deleted),
    }


def _resolve_instructions_path(repo_root: Path, instructions_path: Path) -> Path:
    if instructions_path.is_absolute():
        return instructions_path.resolve()
    return (repo_root / instructions_path).resolve()


def _snapshot_targets(repo_root: Path, instructions_path: Path) -> list[Path]:
    return [
        repo_root / ".taskxroot",
        repo_root / ".taskx" / "project.json",
        repo_root / ".envrc",
        repo_root / "scripts" / "taskx",
        repo_root / "scripts" / "taskx-local",
        instructions_path,
    ]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        while True:
            chunk = file_obj.read(64 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _doctor_summary(report: DoctorReport, out_dir: Path) -> dict[str, Any]:
    return {
        "status": report.status,
        "checks": report.checks,
        "report_paths": {
            "json": str(out_dir / "DOCTOR_REPORT.json"),
            "markdown": str(out_dir / "DOCTOR_REPORT.md"),
        },
    }


def _write_upgrade_report(repo_root: Path, report: dict[str, Any]) -> dict[str, str]:
    report_dir = repo_root / UPGRADE_REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = report_dir / UPGRADE_REPORT_JSON
    md_path = report_dir / UPGRADE_REPORT_MD

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_upgrade_markdown(report), encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
    }


def _render_upgrade_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# PROJECT_UPGRADE_REPORT",
        "",
        f"- repo_root: {report['repo_root']}",
        f"- instructions_path: {report['instructions_path']}",
        f"- mode: {report['mode']}",
        "",
        "## Rails",
        "",
        f"- status: {report['rails_state']['status']}",
        f"- project_id: {report['rails_state']['project_id']}",
        f"- created: {', '.join(report['rails_state']['created']) or 'none'}",
        "",
    ]

    shell_result = report.get("shell_init")
    lines.extend(["## Shell Init", ""])
    if shell_result is None:
        lines.append("- skipped")
    else:
        lines.append(f"- created_files: {len(shell_result['created_files'])}")
        lines.append(f"- skipped_files: {len(shell_result['skipped_files'])}")
        lines.append(f"- direnv_found: {shell_result['direnv_found']}")

    packs_result = report.get("packs_doctor")
    lines.extend(["", "## Packs Doctor", ""])
    if packs_result is None:
        lines.append("- skipped")
    else:
        lines.append(f"- status: {packs_result['status']}")
        lines.append(f"- applied_mode: {packs_result['applied_mode']}")
        lines.append(f"- actions_taken: {len(packs_result['actions_taken'])}")

    doctor_result = report.get("doctor")
    lines.extend(["", "## Doctor", ""])
    if doctor_result is None:
        lines.append("- skipped")
    else:
        lines.append(f"- status: {doctor_result['status']}")
        lines.append(f"- warnings: {doctor_result['checks']['warnings']}")

    changes = report["file_changes"]
    lines.extend(
        [
            "",
            "## File Changes",
            "",
            f"- changed_count: {changes['changed_count']}",
            f"- created: {len(changes['created'])}",
            f"- modified: {len(changes['modified'])}",
            f"- deleted: {len(changes['deleted'])}",
            "",
        ]
    )

    return "\n".join(lines)
