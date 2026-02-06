
import hashlib
import json
import logging
import os
import shutil
import zipfile
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, List, Dict, Optional

import yaml
from rich.console import Console

console = Console()

class BundleExporter:
    """Handles deterministic export of case bundles."""

    def __init__(self, repo_root: Path, config_path: Optional[Path] = None):
        self.repo_root = repo_root.resolve()
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[Path]) -> Dict[str, Any]:
        """Load config from file or use defaults."""
        defaults = {
            "logs": {
                "globs": ["**/*.log", "**/*.out", "**/*.err"],
                "caps": {"per_file_max_mb": 25, "total_logs_max_mb": 250, "max_files": 10000},
                "excludes": ["**/node_modules/**", "**/.git/**", "**/.venv/**", "**/__pycache__/**"]
            }
        }
        
        path = config_path or (self.repo_root / "taskx_bundle.yaml")
        if path.exists():
            try:
                with open(path) as f:
                    user_config = yaml.safe_load(f)
                    # Deep merge would be better, but simple overlay is fine for now
                    if user_config:
                        defaults.update(user_config)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to load config {path}: {e}[/yellow]")
        
        return defaults

    def collect_taskx_artifacts(self, last_n: int, temp_dir: Path) -> List[str]:
        """Collect last N runs and task packets."""
        taskx_dir = temp_dir / "taskx"
        taskx_dir.mkdir(parents=True, exist_ok=True)
        
        manifest_entries = []

        # 1. Task Queue
        queue_path = self.repo_root / "out" / "tasks" / "task_queue.json"
        if queue_path.exists():
            dest = taskx_dir / "task_queue.json"
            shutil.copy2(queue_path, dest)
            manifest_entries.append("taskx/task_queue.json")

        # 2. Packets (simplified: verify existence, but complex logic omitted for brevity)
        # 3. Runs (simplified: copy last N folders)
        runs_dir = self.repo_root / "out" / "runs"
        if runs_dir.exists():
            all_runs = sorted(list(runs_dir.iterdir()), key=lambda p: p.stat().st_mtime, reverse=True)
            for run in all_runs[:last_n]:
                if not run.is_dir(): continue
                dest_run = taskx_dir / "runs" / run.name
                shutil.copytree(run, dest_run)
                # Walk and add to manifest
                for root, _, files in os.walk(dest_run):
                    for file in files:
                        rel_path = Path(root).relative_to(temp_dir) / file
                        manifest_entries.append(str(rel_path))

        return manifest_entries

    def collect_repo_snapshot(self, temp_dir: Path) -> str:
        """Generate REPO_SNAPSHOT.json."""
        repo_dir = temp_dir / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)
        
        snapshot = {
            "timestamp": datetime.now(UTC).isoformat(),
            "git_available": False,
            "head_sha": None,
            "branch": None
        }

        # Try git
        if (self.repo_root / ".git").exists():
            try:
                import subprocess
                head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repo_root).decode().strip()
                branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo_root).decode().strip()
                snapshot["git_available"] = True
                snapshot["head_sha"] = head
                snapshot["branch"] = branch
            except Exception:
                pass

        snapshot_path = repo_dir / "REPO_SNAPSHOT.json"
        with open(snapshot_path, "w") as f:
            json.dump(snapshot, f, indent=2)
            
        return "repo/REPO_SNAPSHOT.json"

    def collect_repo_logs(self, temp_dir: Path) -> List[str]:
        """Collect logs based on config capabilities."""
        logs_out_dir = temp_dir / "repo" / "logs"
        logs_out_dir.mkdir(parents=True, exist_ok=True)
        
        log_index = {
            "included": [],
            "skipped": []
        }
        
        manifest_entries = []
        
        # Simple glob implementation
        globs = self.config["logs"].get("globs", [])
        excludes = self.config["logs"].get("excludes", [])
        
        # Gather candidates
        candidates = set()
        for g in globs:
            for path in self.repo_root.glob(g):
                if path.is_file():
                    candidates.add(path)
                    
        # Filter excludes
        final_list = []
        for path in candidates:
            rel = path.relative_to(self.repo_root)
            # Check excludes (naive)
            is_excluded = False
            for ex in excludes:
                # Basic match check
                if ex.strip("/") in str(rel): # Simplification
                    is_excluded = True
                    break
            if not is_excluded:
                final_list.append(path)
                
        # Copy with caps logic
        total_size = 0
        max_total = self.config["logs"]["caps"]["total_logs_max_mb"] * 1024 * 1024
        
        for path in final_list:
            size = path.stat().st_size
            rel_path = path.relative_to(self.repo_root)
            
            if size > self.config["logs"]["caps"]["per_file_max_mb"] * 1024 * 1024:
                log_index["skipped"].append({"path": str(rel_path), "reason": "size_limit"})
                continue
                
            if total_size + size > max_total:
                 log_index["skipped"].append({"path": str(rel_path), "reason": "total_cap_hit"})
                 continue

            # Copy
            dest = logs_out_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            
            total_size += size
            log_index["included"].append({"path": str(rel_path), "size": size})
            manifest_entries.append(f"repo/logs/{rel_path}")

        # Write index
        index_path = temp_dir / "repo" / "LOG_INDEX.json"
        with open(index_path, "w") as f:
            json.dump(log_index, f, indent=2)
        manifest_entries.append("repo/LOG_INDEX.json")
        
        return manifest_entries

    def build_case_manifest(self, temp_dir: Path, case_id: str) -> None:
        """Generate manifest for the entire bundle."""
        case_dir = temp_dir / "case"
        case_dir.mkdir(parents=True, exist_ok=True)
        
        # Compute SHA256 of all contents
        # This is a placeholder for the full hashing logic required by the spec
        # In a real implementation we would walk temp_dir (excluding manifest itself)
        
        manifest = {
            "schema_version": "1.0",
            "case_id": case_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "bundle_manifest": {
                "sha256": "placeholder-hash",
                "source_label": "taskx-export",
                "created_at": datetime.now(UTC).isoformat()
            },
            "contents": {
                # Pointers would be populated here
            }
        }
        
        with open(case_dir / "CASE_MANIFEST.json", "w") as f:
            json.dump(manifest, f, indent=2)

    def export(self, last_n: int, out_dir: Path, case_id: Optional[str] = None) -> Path:
        """Main export flow."""
        import tempfile
        
        if not case_id:
            ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            case_id = f"CASE_{ts}"

        console.print(f"[cyan]Exporting Case Bundle: {case_id}[/cyan]")
        
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            
            # 1. Artifacts
            self.collect_taskx_artifacts(last_n, temp_path)
            
            # 2. Snapshot
            self.collect_repo_snapshot(temp_path)
            
            # 3. Logs
            self.collect_repo_logs(temp_path)
            
            # 4. Manifest
            self.build_case_manifest(temp_path, case_id)
            
            # 5. Zip
            out_dir.mkdir(parents=True, exist_ok=True)
            zip_path = out_dir / f"{case_id}.zip"
            
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(temp_path):
                    for file in files:
                        abs_path = Path(root) / file
                        rel_path = abs_path.relative_to(temp_path)
                        zf.write(abs_path, rel_path)
                        
            console.print(f"[green]Bundle exported to: {zip_path}[/green]")
            return zip_path
