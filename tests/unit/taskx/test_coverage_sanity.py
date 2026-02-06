"""Coverage sanity tests - ensures real package code is executed during test runs.

These tests are minimal but exercise actual code paths to prevent "no data collected" warnings.
"""
from pathlib import Path

import pytest


class TestTaskXImport:
    """Test that TaskX package can be imported and has expected attributes."""

    def test_taskx_imports(self):
        """TaskX package imports successfully."""
        import taskx

        assert taskx is not None
        assert hasattr(taskx, "__version__")
        assert taskx.__version__ == "0.1.0"

    def test_doctor_module_imports(self):
        """Doctor module imports successfully."""
        from taskx.doctor import DoctorReport, _check_taskx_import

        assert DoctorReport is not None
        assert _check_taskx_import is not None


class TestSchemaRegistry:
    """Test schema registry functionality."""

    def test_schema_registry_initialization(self):
        """Schema registry initializes and discovers schemas."""
        from taskx.utils.schema_registry import SchemaRegistry

        registry = SchemaRegistry()
        assert registry is not None
        assert len(registry.available) > 0
        assert "allowlist_diff" in registry.available

    def test_get_schema_json(self):
        """Can load a schema as JSON."""
        from taskx.utils.schema_registry import get_schema_json

        schema = get_schema_json("allowlist_diff")
        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"


class TestDoctorNonCLI:
    """Test doctor functionality without invoking CLI."""

    def test_check_taskx_import(self):
        """Internal taskx import check works."""
        from taskx.doctor import _check_taskx_import

        result = _check_taskx_import()
        assert result.status == "pass"
        assert "0.1.0" in result.message

    def test_check_schema_registry(self):
        """Internal schema registry check works."""
        from taskx.doctor import _check_schema_registry

        result = _check_schema_registry()
        assert result.status == "pass"
        assert "schemas available" in result.message

    def test_run_doctor_minimal(self, tmp_path: Path):
        """Can run doctor and generate report."""
        from taskx.doctor import run_doctor

        out_dir = tmp_path / "doctor_output"
        out_dir.mkdir()

        report = run_doctor(
            out_dir=out_dir,
            timestamp_mode="deterministic",
            require_git=False,
        )

        # Verify report structure
        assert report is not None
        assert report.status in ("passed", "failed")
        assert report.timestamp_mode == "deterministic"
        assert report.generated_at == "1970-01-01T00:00:00Z"

        # Verify report files were created
        assert (out_dir / "DOCTOR_REPORT.json").exists()
        assert (out_dir / "DOCTOR_REPORT.md").exists()


class TestRepoUtils:
    """Test repository utility functions."""

    def test_find_taskx_repo_root_with_marker(self, tmp_path: Path):
        """Can find TaskX repo root with .taskxroot marker."""
        from taskx.utils.repo import find_taskx_repo_root

        # Create a mock repo with marker
        marker = tmp_path / ".taskxroot"
        marker.touch()

        result = find_taskx_repo_root(tmp_path)
        assert result == tmp_path

    def test_find_taskx_repo_root_no_marker(self, tmp_path: Path):
        """Returns None when no TaskX repo marker found."""
        from taskx.utils.repo import find_taskx_repo_root

        result = find_taskx_repo_root(tmp_path)
        assert result is None

    def test_require_taskx_repo_root_raises(self, tmp_path: Path):
        """Raises helpful error when repo not found."""
        from taskx.utils.repo import require_taskx_repo_root

        with pytest.raises(RuntimeError) as exc_info:
            require_taskx_repo_root(tmp_path)

        assert "TaskX repo not detected" in str(exc_info.value)
        assert "touch .taskxroot" in str(exc_info.value)
