"""TaskX CI gate - Combines doctor checks with promotion validation.

Provides a single deterministic gate for CI/CD pipelines that enforces:
1. TaskX installation is healthy (via doctor checks)
2. Run has valid promotion token (if required)
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TextIO

from taskx.doctor import run_doctor
from taskx.utils.schema_registry import SchemaRegistry


@dataclass
class CheckItem:
    """Individual check result."""

    id: str
    status: Literal["pass", "fail", "warn"]
    message: str
    remediation: list[str] = field(default_factory=list)


@dataclass
class CiGateReport:
    """Complete CI gate report."""

    schema_version: str = "1.0"
    generated_at: str = ""
    timestamp_mode: str = "deterministic"
    status: Literal["passed", "failed"] = "passed"

    # Doctor results
    doctor: dict = field(default_factory=dict)

    # Promotion validation
    promotion: dict = field(default_factory=dict)

    # Check summary
    checks: dict = field(default_factory=dict)


def _get_deterministic_timestamp() -> str:
    """Get deterministic timestamp for testing."""
    return "1970-01-01T00:00:00Z"


def _get_wallclock_timestamp() -> str:
    """Get current wallclock timestamp."""
    return datetime.now(UTC).isoformat()


def _select_latest_run(runs_root: Path) -> Path | None:
    """Select latest run by deterministic folder name sort (descending).

    Args:
        runs_root: Directory containing run folders

    Returns:
        Path to latest run folder, or None if no runs found
    """
    if not runs_root.exists() or not runs_root.is_dir():
        return None

    # List all directories
    run_dirs = [d for d in runs_root.iterdir() if d.is_dir()]

    if not run_dirs:
        return None

    # Sort by name descending (latest first)
    run_dirs.sort(key=lambda p: p.name, reverse=True)

    return run_dirs[0]


def _validate_promotion(
    run_dir: Path,
    promotion_filename: str,
    require_passed: bool
) -> tuple[bool, str | None, list[str]]:
    """Validate promotion token in run directory.

    Args:
        run_dir: Run directory path
        promotion_filename: Name of promotion file (default: PROMOTION.json)
        require_passed: Whether to require status == "passed"

    Returns:
        Tuple of (validated, promotion_status, errors)
        - validated: True if promotion is valid
        - promotion_status: "passed" or "failed" or None
        - errors: List of error messages
    """
    errors = []

    promotion_path = run_dir / promotion_filename

    # Check file exists
    if not promotion_path.exists():
        errors.append(f"Promotion file not found: {promotion_path}")
        return False, None, errors

    # Load JSON
    try:
        with open(promotion_path, encoding="utf-8") as f:
            promotion_data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in promotion file: {e}")
        return False, None, errors
    except Exception as e:
        errors.append(f"Failed to read promotion file: {e}")
        return False, None, errors

    # Validate against schema
    try:
        registry = SchemaRegistry()
        registry.get_json("promotion_token")

        # Simple validation: check required fields
        if not isinstance(promotion_data, dict):
            errors.append("Promotion file is not a JSON object")
            return False, None, errors

        if "status" not in promotion_data:
            errors.append("Promotion file missing 'status' field")
            return False, None, errors

        promotion_status = promotion_data["status"]

        if promotion_status not in ["passed", "failed"]:
            errors.append(f"Invalid promotion status: {promotion_status}")
            return False, None, errors

        # Check if passed status required
        if require_passed and promotion_status != "passed":
            errors.append(f"Promotion status is '{promotion_status}' but 'passed' required")
            return False, promotion_status, errors

        return True, promotion_status, []

    except Exception as e:
        errors.append(f"Schema validation failed: {e}")
        return False, None, errors


def run_ci_gate(
    out_dir: Path,
    timestamp_mode: str = "deterministic",
    require_git: bool = False,
    run_dir: Path | None = None,
    runs_root: Path | None = None,
    promotion_filename: str = "PROMOTION.json",
    require_promotion: bool = True,
    require_promotion_passed: bool = True
) -> CiGateReport:
    """Run CI gate checks (doctor + promotion validation).

    Args:
        out_dir: Directory to write report files
        timestamp_mode: "deterministic" or "wallclock"
        require_git: Whether to require git availability
        run_dir: Optional specific run directory to validate
        runs_root: Optional runs directory to search for latest run
        promotion_filename: Name of promotion file
        require_promotion: Whether to require promotion validation
        require_promotion_passed: Whether to require promotion status == "passed"

    Returns:
        CiGateReport with all check results
    """
    # Initialize report
    report = CiGateReport()
    report.timestamp_mode = timestamp_mode

    if timestamp_mode == "deterministic":
        report.generated_at = _get_deterministic_timestamp()
    else:
        report.generated_at = _get_wallclock_timestamp()

    # Collect all checks
    checks: list[CheckItem] = []

    # ========================================
    # CHECK 1: Run doctor
    # ========================================

    # Create temp directory for doctor report
    doctor_out = out_dir / "doctor"

    try:
        doctor_report = run_doctor(
            out_dir=doctor_out,
            timestamp_mode=timestamp_mode,
            require_git=require_git
        )

        doctor_status = doctor_report.status
        missing_schemas = doctor_report.schemas.get("missing", [])

        report.doctor = {
            "status": doctor_status,
            "report_path": str(doctor_out / "DOCTOR_REPORT.json"),
            "missing_schemas": missing_schemas
        }

        if doctor_status == "passed":
            checks.append(CheckItem(
                id="doctor",
                status="pass",
                message="Doctor checks passed",
                remediation=[]
            ))
        else:
            checks.append(CheckItem(
                id="doctor",
                status="fail",
                message=f"Doctor checks failed. Missing schemas: {missing_schemas}",
                remediation=[
                    f"See doctor report: {doctor_out / 'DOCTOR_REPORT.md'}",
                    "Fix schema packaging in pyproject.toml",
                    "Reinstall: pip install --force-reinstall -e ."
                ]
            ))

    except Exception as e:
        report.doctor = {
            "status": "failed",
            "report_path": None,
            "missing_schemas": []
        }
        checks.append(CheckItem(
            id="doctor",
            status="fail",
            message=f"Doctor run failed: {e}",
            remediation=["Check TaskX installation"]
        ))

    # ========================================
    # CHECK 2: Promotion validation
    # ========================================

    promotion_validated = False
    promotion_status_value = None
    promotion_errors = []
    selected_run_dir = None
    promotion_path_str = None

    if require_promotion:
        # Determine run directory
        if run_dir:
            selected_run_dir = run_dir
        elif runs_root:
            selected_run_dir = _select_latest_run(runs_root)
            if not selected_run_dir:
                promotion_errors.append(f"No runs found in {runs_root}")
        else:
            promotion_errors.append("Promotion required but no run directory specified (use --run or --runs-root)")

        # Validate if we have a run directory
        if selected_run_dir and not promotion_errors:
            promotion_validated, promotion_status_value, promotion_errors = _validate_promotion(
                run_dir=selected_run_dir,
                promotion_filename=promotion_filename,
                require_passed=require_promotion_passed
            )
            promotion_path_str = str(selected_run_dir / promotion_filename)

        # Create check item
        if promotion_validated:
            checks.append(CheckItem(
                id="promotion",
                status="pass",
                message=f"Promotion validated: status={promotion_status_value}",
                remediation=[]
            ))
        else:
            checks.append(CheckItem(
                id="promotion",
                status="fail",
                message=f"Promotion validation failed: {'; '.join(promotion_errors)}",
                remediation=[
                    f"Run directory: {selected_run_dir or 'not found'}",
                    f"Expected promotion file: {promotion_filename}",
                    "Ensure run has completed promotion gate successfully",
                    "Run: taskx promote-run --run <run_dir>"
                ]
            ))

    # Store promotion info in report
    report.promotion = {
        "required": require_promotion,
        "validated": promotion_validated,
        "run_dir": str(selected_run_dir) if selected_run_dir else None,
        "promotion_path": promotion_path_str,
        "promotion_status": promotion_status_value,
        "errors": promotion_errors
    }

    # ========================================
    # Summarize checks
    # ========================================

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

    json_path = out_dir / "CI_GATE_REPORT.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2, sort_keys=True)

    md_path = out_dir / "CI_GATE_REPORT.md"
    with open(md_path, "w", encoding="utf-8") as f:
        _write_markdown_report(f, report, checks)

    return report


def _write_markdown_report(f: TextIO, report: CiGateReport, checks: list[CheckItem]) -> None:
    """Write human-readable markdown report."""
    f.write("# TaskX CI Gate Report\n\n")

    # Status
    status_emoji = "✅" if report.status == "passed" else "❌"
    f.write(f"**Status**: {status_emoji} {report.status.upper()}\n\n")

    # Summary
    f.write(f"**Generated**: {report.generated_at} ({report.timestamp_mode})\n\n")
    f.write("## Summary\n\n")
    f.write(f"- Passed: {report.checks['passed']}\n")
    f.write(f"- Failed: {report.checks['failed']}\n")
    f.write(f"- Warnings: {report.checks['warnings']}\n\n")

    # Doctor
    f.write("## Doctor Checks\n\n")
    doctor_emoji = "✅" if report.doctor["status"] == "passed" else "❌"
    f.write(f"**Status**: {doctor_emoji} {report.doctor['status']}\n\n")

    if report.doctor["missing_schemas"]:
        f.write(f"**Missing Schemas**: {', '.join(report.doctor['missing_schemas'])}\n\n")

    if report.doctor["report_path"]:
        f.write(f"**Report**: `{report.doctor['report_path']}`\n\n")

    # Promotion
    f.write("## Promotion Validation\n\n")

    if report.promotion["required"]:
        promo_emoji = "✅" if report.promotion["validated"] else "❌"
        f.write("**Required**: Yes\n")
        f.write(f"**Validated**: {promo_emoji} {report.promotion['validated']}\n")

        if report.promotion["run_dir"]:
            f.write(f"**Run Directory**: `{report.promotion['run_dir']}`\n")

        if report.promotion["promotion_path"]:
            f.write(f"**Promotion File**: `{report.promotion['promotion_path']}`\n")

        if report.promotion["promotion_status"]:
            f.write(f"**Promotion Status**: {report.promotion['promotion_status']}\n")

        if report.promotion["errors"]:
            f.write("\n**Errors**:\n")
            for error in report.promotion["errors"]:
                f.write(f"- {error}\n")

        f.write("\n")
    else:
        f.write("**Required**: No (skipped)\n\n")

    # Checks
    f.write("## Detailed Checks\n\n")
    for check in checks:
        status_symbol = {"pass": "✅", "fail": "❌", "warn": "⚠️"}[check.status]
        f.write(f"### {status_symbol} {check.id}\n\n")
        f.write(f"{check.message}\n\n")

        if check.remediation:
            f.write("**Remediation:**\n\n")
            for step in check.remediation:
                f.write(f"- {step}\n")
            f.write("\n")

    # Exit code guidance
    f.write("## Exit Code\n\n")
    if report.status == "passed":
        f.write("0 (success - gate passed)\n")
    else:
        f.write("2 (policy violation - gate failed)\n")
