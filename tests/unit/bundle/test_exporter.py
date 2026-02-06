
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from taskx.pipeline.bundle.exporter import BundleExporter

class TestBundleExporter:
    """Test bundle export logic."""

    @pytest.fixture
    def repo_root(self, tmp_path):
        """Create a mock repo root."""
        root = tmp_path / "repo"
        root.mkdir()
        
        # Create output dirs
        (root / "out" / "runs").mkdir(parents=True)
        (root / "out" / "tasks").mkdir(parents=True)
        
        # Create dummy artifacts
        (root / "out" / "tasks" / "task_queue.json").write_text("{}")
        
        # Create dummy logs
        (root / "app.log").write_text("dummy log content")
        
        return root

    def test_collect_repo_snapshot(self, repo_root):
        """Should generate REPO_SNAPSHOT.json."""
        exporter = BundleExporter(repo_root)
        with patch("tempfile.TemporaryDirectory") as mock_temp:
             # We test the method directly, passing a path
             temp_dir = repo_root / "temp"
             temp_dir.mkdir()
             
             path = exporter.collect_repo_snapshot(temp_dir)
             assert path == "repo/REPO_SNAPSHOT.json"
             
             snapshot_file = temp_dir / "repo" / "REPO_SNAPSHOT.json"
             assert snapshot_file.exists()
             data = json.loads(snapshot_file.read_text())
             assert "timestamp" in data
             assert "git_available" in data

    def test_collect_repo_logs_caps(self, repo_root):
        """Should respect log caps."""
        exporter = BundleExporter(repo_root)
        
        # Create a large log file
        large_log = repo_root / "large.log"
        # 1MB
        large_log.write_text("a" * 1024 * 1024) 
        
        # Config to limit to 500KB
        exporter.config["logs"]["caps"]["per_file_max_mb"] = 0.5
        
        temp_dir = repo_root / "temp_logs"
        temp_dir.mkdir()
        
        exporter.collect_repo_logs(temp_dir)
        
        index_file = temp_dir / "repo" / "LOG_INDEX.json"
        assert index_file.exists()
        
        data = json.loads(index_file.read_text())
        # Should be skipped
        skipped = [x for x in data["skipped"] if x["path"] == "large.log"]
        assert len(skipped) == 1
        assert skipped[0]["reason"] == "size_limit"

    def test_export_creates_zip(self, repo_root):
        """Should create a zip bundle."""
        exporter = BundleExporter(repo_root)
        dest_dir = repo_root / "dest"
        
        zip_path = exporter.export(last_n=1, out_dir=dest_dir, case_id="CASE_TEST")
        
        assert zip_path.exists()
        assert zip_path.name == "CASE_TEST.zip"
        
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "repo/REPO_SNAPSHOT.json" in names
            assert "case/CASE_MANIFEST.json" in names
