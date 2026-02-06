"""Tests for TaskX repo guard functionality."""
from pathlib import Path

import pytest

from taskx.utils.repo import find_taskx_repo_root, require_taskx_repo_root


class TestFindTaskXRepoRoot:
    """Tests for find_taskx_repo_root()."""

    def test_finds_taskxroot_marker(self, tmp_path: Path):
        """Should find repo root with .taskxroot marker."""
        marker = tmp_path / ".taskxroot"
        marker.touch()

        subdir = tmp_path / "subdir" / "nested" / "deep"
        subdir.mkdir(parents=True)

        result = find_taskx_repo_root(subdir)
        assert result == tmp_path

    def test_finds_pyproject_with_taskx_name(self, tmp_path: Path):
        """Should find repo root with pyproject.toml name='taskx'."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "taskx"\n')

        subdir = tmp_path / "src"
        subdir.mkdir()

        result = find_taskx_repo_root(subdir)
        assert result == tmp_path

    def test_prefers_taskxroot_over_pyproject(self, tmp_path: Path):
        """Should prefer .taskxroot marker over pyproject.toml at same level."""
        # Both markers at the same level - .taskxroot should win
        (tmp_path / ".taskxroot").touch()
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "taskx"\n')

        subdir = tmp_path / "nested"
        subdir.mkdir()

        result = find_taskx_repo_root(subdir)
        assert result == tmp_path

    def test_returns_none_without_marker(self, tmp_path: Path):
        """Should return None when no marker found."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = find_taskx_repo_root(subdir)
        assert result is None

    def test_ignores_invalid_pyproject(self, tmp_path: Path):
        """Should ignore pyproject.toml with invalid TOML."""
        (tmp_path / "pyproject.toml").write_text('[invalid toml...\n')

        result = find_taskx_repo_root(tmp_path)
        assert result is None

    def test_ignores_pyproject_without_taskx_name(self, tmp_path: Path):
        """Should ignore pyproject.toml with different project name."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "other-project"\n')

        result = find_taskx_repo_root(tmp_path)
        assert result is None


class TestRequireTaskXRepoRoot:
    """Tests for require_taskx_repo_root()."""

    def test_returns_path_when_found(self, tmp_path: Path):
        """Should return path when repo found."""
        (tmp_path / ".taskxroot").touch()

        result = require_taskx_repo_root(tmp_path)
        assert result == tmp_path

    def test_raises_with_helpful_message(self, tmp_path: Path):
        """Should raise RuntimeError with remediation steps."""
        with pytest.raises(RuntimeError) as exc_info:
            require_taskx_repo_root(tmp_path)

        error_msg = str(exc_info.value)
        assert "TaskX repo not detected" in error_msg
        assert "touch .taskxroot" in error_msg
        assert "--no-repo-guard" in error_msg


class TestRepoGuardIntegration:
    """Integration tests for repo guard in real scenarios."""

    def test_nested_project_structure(self, tmp_path: Path):
        """Should work in nested project structures."""
        root = tmp_path / "my-project"
        root.mkdir()
        (root / ".taskxroot").touch()

        src = root / "src" / "taskx" / "pipeline"
        src.mkdir(parents=True)

        tests = root / "tests" / "unit" / "pipeline"
        tests.mkdir(parents=True)

        assert find_taskx_repo_root(src) == root
        assert find_taskx_repo_root(tests) == root
        assert find_taskx_repo_root(root) == root

    def test_multiple_projects_side_by_side(self, tmp_path: Path):
        """Should not confuse adjacent projects."""
        proj1 = tmp_path / "project1"
        proj1.mkdir()
        (proj1 / ".taskxroot").touch()

        proj2 = tmp_path / "project2"
        proj2.mkdir()
        (proj2 / ".taskxroot").touch()

        assert find_taskx_repo_root(proj1) == proj1
        assert find_taskx_repo_root(proj2) == proj2
