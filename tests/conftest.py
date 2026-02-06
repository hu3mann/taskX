"""Pytest configuration and fixtures for TaskX tests."""
from pathlib import Path

import pytest


def pytest_sessionfinish(session, exitstatus):
    """Check that coverage data was collected if --cov was requested.

    This prevents silent "no data collected" scenarios that produce 0% coverage
    without failing the test run.
    """
    # Check if coverage was requested
    cov_enabled = any("--cov" in str(arg) for arg in session.config.args)

    if not cov_enabled:
        # Coverage not requested, nothing to check
        return

    # Look for coverage data files
    cwd = Path.cwd()
    coverage_files = list(cwd.glob(".coverage*"))

    if not coverage_files:
        # No coverage data collected - this is a failure
        pytest.exit(
            "Coverage was enabled but no data was collected. "
            "This suggests tests are not importing/executing package code. "
            "Check that tests import from 'taskx' (the package) not 'src/taskx' (filesystem path).",
            returncode=1
        )
