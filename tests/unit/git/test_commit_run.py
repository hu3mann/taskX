"""Tests for taskx commit-run functionality."""
import json
import subprocess
from pathlib import Path

import pytest

from taskx.git.commit_run import commit_run


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    readme = repo / "README.md"
    readme.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    return repo


@pytest.fixture
def run_dir_with_allowlist(git_repo: Path) -> Path:
    """Create a run directory with a passing allowlist report."""
    run_dir = git_repo / "out" / "runs" / "RUN_001"
    run_dir.mkdir(parents=True)

    # Create a passing allowlist report
    allowed_file = git_repo / "src" / "module.py"
    allowed_file.parent.mkdir(parents=True, exist_ok=True)

    allowlist_data = {
        "status": "passed",
        "violations": [],
        "allowed_files": [str(allowed_file.relative_to(git_repo))],
    }

    allowlist_path = run_dir / "ALLOWLIST_DIFF.json"
    with open(allowlist_path, "w") as f:
        json.dump(allowlist_data, f)

    return run_dir


@pytest.fixture
def run_dir_with_promotion(run_dir_with_allowlist: Path) -> Path:
    """Add promotion token to run directory."""
    promotion_data = {
        "token": "abc123def456",
        "status": "passed",
        "promoted_at": "2025-02-05T15:00:00Z",
    }

    promotion_path = run_dir_with_allowlist / "PROMOTION.json"
    with open(promotion_path, "w") as f:
        json.dump(promotion_data, f)

    return run_dir_with_allowlist


class TestCommitRunHappyPath:
    """Test successful commit creation."""

    def test_creates_commit_with_allowlisted_file(
        self, git_repo: Path, run_dir_with_promotion: Path
    ):
        """Should create commit when all conditions are met."""
        # Modify an allowlisted file
        allowed_file = git_repo / "src" / "module.py"
        allowed_file.write_text("print('hello world')\n")

        # Run commit_run
        report = commit_run(
            run_dir=run_dir_with_promotion,
            message=None,
            allow_unpromoted=False,
            timestamp_mode="deterministic",
        )

        # Verify success
        assert report["status"] == "passed"
        assert report["git"]["commit_created"] is True
        assert report["git"]["head_after"] is not None
        assert report["git"]["head_after"] != report["git"]["head_before"]
        assert len(report["allowlist"]["staged_files"]) == 1
        assert "src/module.py" in report["allowlist"]["staged_files"]

        # Verify commit message format
        expected_msg = "TASKX commit-run | run=RUN_001 | promo=abc123def456"
        assert report["git"]["commit_message"] == expected_msg

        # Verify report was written
        report_path = run_dir_with_promotion / "COMMIT_RUN.json"
        assert report_path.exists()

    def test_uses_custom_message(self, git_repo: Path, run_dir_with_promotion: Path):
        """Should use custom commit message when provided."""
        # Modify an allowlisted file
        allowed_file = git_repo / "src" / "module.py"
        allowed_file.write_text("print('custom')\n")

        # Run with custom message
        custom_msg = "feat: implement task packet A18"
        report = commit_run(
            run_dir=run_dir_with_promotion,
            message=custom_msg,
            allow_unpromoted=False,
            timestamp_mode="deterministic",
        )

        assert report["status"] == "passed"
        assert report["git"]["commit_message"] == custom_msg


class TestCommitRunRejectViolations:
    """Test rejection when allowlist has violations."""

    def test_rejects_commit_with_violations(self, git_repo: Path):
        """Should refuse to commit when allowlist has violations."""
        run_dir = git_repo / "out" / "runs" / "RUN_002"
        run_dir.mkdir(parents=True)

        # Create allowlist report with violations
        allowlist_data = {
            "status": "failed",
            "violations": [
                {"path": "unauthorized.py", "reason": "not in allowlist"}
            ],
            "allowed_files": ["src/module.py"],
        }

        allowlist_path = run_dir / "ALLOWLIST_DIFF.json"
        with open(allowlist_path, "w") as f:
            json.dump(allowlist_data, f)

        # Add promotion token
        promotion_data = {"token": "test123"}
        with open(run_dir / "PROMOTION.json", "w") as f:
            json.dump(promotion_data, f)

        # Run commit_run
        report = commit_run(
            run_dir=run_dir,
            message=None,
            allow_unpromoted=False,
            timestamp_mode="deterministic",
        )

        # Verify failure
        assert report["status"] == "failed"
        assert report["git"]["commit_created"] is False
        assert len(report["errors"]) > 0
        assert any("violation" in error.lower() for error in report["errors"])


class TestCommitRunRejectUnpromoted:
    """Test rejection when run is not promoted."""

    def test_rejects_unpromoted_run_by_default(
        self, git_repo: Path, run_dir_with_allowlist: Path
    ):
        """Should refuse to commit unpromoted run without override."""
        # Modify an allowlisted file
        allowed_file = git_repo / "src" / "module.py"
        allowed_file.write_text("print('test')\n")

        # Run without promotion token (and without allow_unpromoted)
        report = commit_run(
            run_dir=run_dir_with_allowlist,
            message=None,
            allow_unpromoted=False,
            timestamp_mode="deterministic",
        )

        # Verify failure
        assert report["status"] == "failed"
        assert report["promotion"]["found"] is False
        assert report["git"]["commit_created"] is False
        assert any("not promoted" in error.lower() for error in report["errors"])

    def test_allows_unpromoted_with_override(
        self, git_repo: Path, run_dir_with_allowlist: Path
    ):
        """Should allow commit of unpromoted run when explicitly overridden."""
        # Modify an allowlisted file
        allowed_file = git_repo / "src" / "module.py"
        allowed_file.write_text("print('override')\n")

        # Run with allow_unpromoted=True
        report = commit_run(
            run_dir=run_dir_with_allowlist,
            message=None,
            allow_unpromoted=True,
            timestamp_mode="deterministic",
        )

        # Verify success
        assert report["status"] == "passed"
        assert report["promotion"]["found"] is False
        assert report["promotion"]["required"] is False
        assert report["git"]["commit_created"] is True


class TestCommitRunRejectNonGitRepo:
    """Test rejection when not in a git repository."""

    def test_rejects_non_git_directory(self, tmp_path: Path):
        """Should fail cleanly when not in a git repo."""
        # Create run dir without git
        non_git_dir = tmp_path / "non_git"
        non_git_dir.mkdir()

        run_dir = non_git_dir / "out" / "runs" / "RUN_003"
        run_dir.mkdir(parents=True)

        # Create minimal allowlist
        allowlist_data = {
            "status": "passed",
            "violations": [],
            "allowed_files": ["test.txt"],
        }
        with open(run_dir / "ALLOWLIST_DIFF.json", "w") as f:
            json.dump(allowlist_data, f)

        # Add promotion
        with open(run_dir / "PROMOTION.json", "w") as f:
            json.dump({"token": "test"}, f)

        # Run commit_run
        report = commit_run(
            run_dir=run_dir,
            message=None,
            allow_unpromoted=False,
            timestamp_mode="deterministic",
        )

        # Verify failure
        assert report["status"] == "failed"
        assert report["git"]["commit_created"] is False
        assert any("git" in error.lower() for error in report["errors"])


class TestCommitRunEdgeCases:
    """Test edge cases and error conditions."""

    def test_fails_when_run_dir_missing(self, git_repo: Path):
        """Should fail when run directory doesn't exist."""
        nonexistent = git_repo / "out" / "runs" / "NONEXISTENT"

        report = commit_run(
            run_dir=nonexistent,
            message=None,
            allow_unpromoted=False,
            timestamp_mode="deterministic",
        )

        assert report["status"] == "failed"
        assert any("does not exist" in error for error in report["errors"])

    def test_fails_when_allowlist_missing(self, git_repo: Path):
        """Should fail when ALLOWLIST_DIFF.json is missing."""
        run_dir = git_repo / "out" / "runs" / "RUN_004"
        run_dir.mkdir(parents=True)
        # No allowlist file created

        report = commit_run(
            run_dir=run_dir,
            message=None,
            allow_unpromoted=True,
            timestamp_mode="deterministic",
        )

        assert report["status"] == "failed"
        assert any("allowlist" in error.lower() for error in report["errors"])

    def test_fails_when_no_files_to_stage(
        self, git_repo: Path, run_dir_with_promotion: Path
    ):
        """Should fail when no allowlisted files are modified."""
        # Don't modify any files - everything is already committed

        report = commit_run(
            run_dir=run_dir_with_promotion,
            message=None,
            allow_unpromoted=False,
            timestamp_mode="deterministic",
        )

        assert report["status"] == "failed"
        assert any("no modified files" in error.lower() for error in report["errors"])

    def test_deterministic_timestamp(self, git_repo: Path, run_dir_with_promotion: Path):
        """Should use deterministic timestamp when requested."""
        # Modify file
        allowed_file = git_repo / "src" / "module.py"
        allowed_file.write_text("print('deterministic')\n")

        report = commit_run(
            run_dir=run_dir_with_promotion,
            message=None,
            allow_unpromoted=False,
            timestamp_mode="deterministic",
        )

        assert report["timestamp_mode"] == "deterministic"
        assert report["generated_at"] == "1970-01-01T00:00:00Z"
