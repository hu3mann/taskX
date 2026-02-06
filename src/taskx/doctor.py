"""TaskX installation integrity checker (doctor command).

Validates that TaskX is correctly installed and can access all required
package data, with special attention to schema bundling issues.
"""

import json
import platform
import shutil
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TextIO

from taskx.utils.schema_registry import SchemaRegistry


@dataclass
class CheckItem:
    """Individual check result."""

    id: str
    status: Literal["pass", "fail", "warn"]
    message: str
    remediation: list[str] = field(default_factory=list)


@dataclass
class DoctorReport:
    """Complete doctor check report."""

    schema_version: str = "1.0"
    generated_at: str = ""
    timestamp_mode: str = "deterministic"
    status: Literal["passed", "failed"] = "passed"

    # Environment info
    environment: dict = field(default_factory=dict)

    # TaskX info
    taskx: dict = field(default_factory=dict)

    # Schema info
    schemas: dict = field(default_factory=dict)

    # Load test result
    load_test: dict = field(default_factory=dict)

    # Repo detection
    repo: dict = field(default_factory=dict)

    # Git availability
    git: dict = field(default_factory=dict)

    # Check summary
    checks: dict = field(default_factory=dict)


def _get_deterministic_timestamp() -> str:
    """Get deterministic timestamp for testing."""
    return "1970-01-01T00:00:00Z"


def _get_wallclock_timestamp() -> str:
    """Get current wallclock timestamp."""
    return datetime.now(UTC).isoformat()


def _check_taskx_import() -> CheckItem:
    """Check A: TaskX import sanity."""
    try:
        import taskx
        version = getattr(taskx, "__version__", None)

        return CheckItem(
            id="taskx_import",
            status="pass",
            message=f"TaskX imports successfully (version: {version or 'unknown'})",
            remediation=[]
        )
    except Exception as e:
        return CheckItem(
            id="taskx_import",
            status="fail",
            message=f"Failed to import TaskX: {e}",
            remediation=[
                "Ensure TaskX is installed: pip install -e . or pip install taskx",
                "Check Python version is 3.11+",
                "Verify virtual environment is activated if using one"
            ]
        )


def _check_schema_registry() -> CheckItem:
    """Check B: Schema registry availability (critical)."""
    try:
        registry = SchemaRegistry()
        available = set(registry.available)

        required = {
            "allowlist_diff",
            "promotion_token",
            "run_envelope",
            "run_summary"
        }

        missing = required - available

        if missing:
            return CheckItem(
                id="schema_registry",
                status="fail",
                message=f"Missing required schemas: {sorted(missing)}. Found: {len(available)} schemas",
                remediation=[
                    "Schema bundling is broken in wheel packaging.",
                    "Fix pyproject.toml to include taskx_schemas as a package:",
                    "",
                    "[tool.hatch.build.targets.wheel]",
                    'packages = ["src/taskx", "taskx_schemas"]',
                    "",
                    "Ensure taskx_schemas/__init__.py exists to make it a proper package.",
                    "Then reinstall: pip install --force-reinstall -e ."
                ]
            )

        return CheckItem(
            id="schema_registry",
            status="pass",
            message=f"Schema registry OK: {len(available)} schemas available",
            remediation=[]
        )

    except Exception as e:
        return CheckItem(
            id="schema_registry",
            status="fail",
            message=f"Schema registry failure: {e}",
            remediation=[
                "Critical failure accessing schema registry.",
                "This indicates a broken TaskX installation.",
                "Try: pip install --force-reinstall -e .",
                "If problem persists, check that taskx_schemas/ exists with __init__.py"
            ]
        )


def _check_schema_load() -> CheckItem:
    """Check C: Validate can load and parse a schema."""
    try:
        registry = SchemaRegistry()

        # Try to load a known schema
        schema = registry.get_json("allowlist_diff")

        # Verify it's actually a schema
        if not isinstance(schema, dict):
            return CheckItem(  # type: ignore[unreachable]
                id="schema_load",
                status="fail",
                message=f"Schema loaded but is not a dict: {type(schema)}",
                remediation=[
                    "Schema file may be corrupted.",
                    "Reinstall TaskX: pip install --force-reinstall -e ."
                ]
            )

        # Check for standard schema fields
        has_schema_fields = any(k in schema for k in ["schema_version", "$schema", "type", "properties"])
        if not has_schema_fields:
            return CheckItem(
                id="schema_load",
                status="warn",
                message="Schema loaded but doesn't have standard JSON Schema fields",
                remediation=[]
            )

        return CheckItem(
            id="schema_load",
            status="pass",
            message="Schema loading and parsing works correctly",
            remediation=[]
        )

    except KeyError as e:
        return CheckItem(
            id="schema_load",
            status="fail",
            message=f"Schema not found: {e}",
            remediation=[
                "Required schema is missing from package data.",
                "Check schema bundling in pyproject.toml",
                "Reinstall: pip install --force-reinstall -e ."
            ]
        )
    except Exception as e:
        return CheckItem(
            id="schema_load",
            status="fail",
            message=f"Failed to load schema: {e}",
            remediation=[
                "Schema loading infrastructure may be broken.",
                "Reinstall TaskX: pip install --force-reinstall -e ."
            ]
        )


def _check_repo_detection(repo_root: Path | None, project_root: Path | None) -> CheckItem:
    """Check D: Repo scope detection (optional)."""
    # This is optional - we just report what we detect
    detected_repo = None
    marker = None

    if repo_root and repo_root.exists():
        detected_repo = repo_root
        marker = "provided"
    else:
        # Try to detect from CWD
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".git").exists():
                detected_repo = parent
                marker = ".git"
                break

    if detected_repo:
        return CheckItem(
            id="repo_detection",
            status="pass",
            message=f"Repo detected at {detected_repo} (via {marker})",
            remediation=[]
        )
    else:
        return CheckItem(
            id="repo_detection",
            status="warn",
            message="No repository detected (not required for TaskX operation)",
            remediation=[]
        )


def _check_git_availability(repo_root: Path | None, require_git: bool) -> CheckItem:
    """Check E: Git availability (optional)."""
    # Check for git executable
    git_exe = shutil.which("git")
    git_exe_found = git_exe is not None

    # Check for git repo
    git_repo_found = False
    if repo_root and (repo_root / ".git").exists() or (Path.cwd() / ".git").exists():
        git_repo_found = True

    git_ok = git_exe_found and git_repo_found

    if require_git and not git_ok:
        return CheckItem(
            id="git_availability",
            status="fail",
            message=f"Git required but not available (exe: {git_exe_found}, repo: {git_repo_found})",
            remediation=[
                "Install git if executable not found",
                "Run from within a git repository if --require-git is set"
            ]
        )
    elif git_ok:
        return CheckItem(
            id="git_availability",
            status="pass",
            message="Git is available and repository detected",
            remediation=[]
        )
    else:
        return CheckItem(
            id="git_availability",
            status="warn",
            message=f"Git not fully available (exe: {git_exe_found}, repo: {git_repo_found})",
            remediation=[]
        )


def run_doctor(
    out_dir: Path,
    timestamp_mode: str = "deterministic",
    require_git: bool = False,
    repo_root: Path | None = None,
    project_root: Path | None = None
) -> DoctorReport:
    """Run TaskX installation integrity checks.

    Args:
        out_dir: Directory to write report files
        timestamp_mode: "deterministic" or "wallclock"
        require_git: Whether to require git availability
        repo_root: Optional repository root path
        project_root: Optional project root path

    Returns:
        DoctorReport with all check results
    """
    # Initialize report
    report = DoctorReport()
    report.timestamp_mode = timestamp_mode

    if timestamp_mode == "deterministic":
        report.generated_at = _get_deterministic_timestamp()
    else:
        report.generated_at = _get_wallclock_timestamp()

    # Collect environment info
    report.environment = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cwd": str(Path.cwd())
    }

    # Run checks
    checks: list[CheckItem] = []

    # Check A: TaskX import
    check_a = _check_taskx_import()
    checks.append(check_a)

    # Extract TaskX version for report
    try:
        import taskx
        version = getattr(taskx, "__version__", None)
        report.taskx = {
            "import_ok": check_a.status == "pass",
            "version": version
        }
    except Exception:
        report.taskx = {
            "import_ok": False,
            "version": None
        }

    # Check B: Schema registry (critical)
    check_b = _check_schema_registry()
    checks.append(check_b)

    # Collect schema info
    try:
        registry = SchemaRegistry()
        required = ["allowlist_diff", "promotion_token", "run_envelope", "run_summary"]
        available = list(registry.available)
        missing = [s for s in required if s not in available]

        report.schemas = {
            "available": available,
            "required": required,
            "missing": missing
        }
    except Exception:
        report.schemas = {
            "available": [],
            "required": ["allowlist_diff", "promotion_token", "run_envelope", "run_summary"],
            "missing": ["allowlist_diff", "promotion_token", "run_envelope", "run_summary"]
        }

    # Check C: Schema load test
    check_c = _check_schema_load()
    checks.append(check_c)

    report.load_test = {
        "name": "allowlist_diff",
        "ok": check_c.status == "pass"
    }

    # Check D: Repo detection (optional)
    check_d = _check_repo_detection(repo_root, project_root)
    checks.append(check_d)

    detected_repo = None
    marker = None
    if repo_root and repo_root.exists():
        detected_repo = str(repo_root)
        marker = "provided"
    else:
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".git").exists():
                detected_repo = str(parent)
                marker = ".git"
                break

    report.repo = {
        "repo_root": detected_repo,
        "project_root": str(project_root) if project_root else None,
        "marker": marker
    }

    # Check E: Git availability
    check_e = _check_git_availability(repo_root, require_git)
    checks.append(check_e)

    git_exe = shutil.which("git") is not None
    git_repo = False
    if detected_repo and Path(detected_repo, ".git").exists() or (Path.cwd() / ".git").exists():
        git_repo = True

    report.git = {
        "git_exe_found": git_exe,
        "git_repo_found": git_repo,
        "ok": git_exe and git_repo
    }

    # Summarize checks
    passed = sum(1 for c in checks if c.status == "pass")
    failed = sum(1 for c in checks if c.status == "fail")
    warnings = sum(1 for c in checks if c.status == "warn")

    report.checks = {
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "items": [asdict(c) for c in checks]
    }

    # Overall status
    report.status = "passed" if failed == 0 else "failed"

    # Write reports
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "DOCTOR_REPORT.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2, sort_keys=True)

    md_path = out_dir / "DOCTOR_REPORT.md"
    with open(md_path, "w", encoding="utf-8") as f:
        _write_markdown_report(f, report, checks)

    return report


def _write_markdown_report(f: TextIO, report: DoctorReport, checks: list[CheckItem]) -> None:
    """Write human-readable markdown report."""
    f.write("# TaskX Doctor Report\n\n")

    # Status
    status_emoji = "✅" if report.status == "passed" else "❌"
    f.write(f"**Status**: {status_emoji} {report.status.upper()}\n\n")

    # Summary
    f.write(f"**Generated**: {report.generated_at} ({report.timestamp_mode})\n\n")
    f.write("## Summary\n\n")
    f.write(f"- Passed: {report.checks['passed']}\n")
    f.write(f"- Failed: {report.checks['failed']}\n")
    f.write(f"- Warnings: {report.checks['warnings']}\n\n")

    # Environment
    f.write("## Environment\n\n")
    f.write(f"- Python: {report.environment['python_version']}\n")
    f.write(f"- Platform: {report.environment['platform']}\n")
    f.write(f"- Working Directory: `{report.environment['cwd']}`\n\n")

    # TaskX
    f.write("## TaskX\n\n")
    f.write(f"- Import OK: {report.taskx['import_ok']}\n")
    f.write(f"- Version: {report.taskx['version'] or 'unknown'}\n\n")

    # Schemas
    f.write("## Schemas\n\n")
    f.write(f"- Available: {len(report.schemas['available'])}\n")
    f.write(f"- Required: {len(report.schemas['required'])}\n")

    if report.schemas['missing']:
        f.write(f"- **Missing**: {', '.join(report.schemas['missing'])}\n\n")
    else:
        f.write("- Missing: none ✅\n\n")

    # Checks
    f.write("## Checks\n\n")
    for check in checks:
        status_symbol = {"pass": "✅", "fail": "❌", "warn": "⚠️"}[check.status]
        f.write(f"### {status_symbol} {check.id}\n\n")
        f.write(f"{check.message}\n\n")

        if check.remediation:
            f.write("**Remediation:**\n\n")
            for step in check.remediation:
                if step:  # Skip empty lines in list
                    f.write(f"- {step}\n")
                else:
                    f.write("\n")
            f.write("\n")

    # Exit code guidance
    f.write("## Exit Code\n\n")
    if report.status == "passed":
        f.write("0 (success)\n")
    else:
        f.write("2 (checks failed)\n")
