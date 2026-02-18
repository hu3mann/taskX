"""Invariants: UI env toggles must not mutate artifact bytes."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _run_doctor(out_dir: Path, env_overrides: dict[str, str]) -> None:
    env = os.environ.copy()
    env.update(env_overrides)
    cmd = [
        sys.executable,
        "-m",
        "taskx",
        "doctor",
        "--timestamp-mode",
        "deterministic",
        "--out",
        str(out_dir),
    ]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"doctor failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def _artifact_hashes(out_dir: Path) -> dict[str, str]:
    files = sorted(path for path in out_dir.rglob("*") if path.is_file())
    hashes: dict[str, str] = {}
    for path in files:
        rel = str(path.relative_to(out_dir))
        hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def test_taskx_neon_does_not_change_artifact_bytes(tmp_path: Path) -> None:
    out_a = tmp_path / "neon_off"
    out_b = tmp_path / "neon_on"
    _run_doctor(out_a, {"TASKX_NEON": "0"})
    _run_doctor(out_b, {"TASKX_NEON": "1"})
    assert _artifact_hashes(out_a) == _artifact_hashes(out_b)


def test_taskx_strict_does_not_change_artifact_bytes(tmp_path: Path) -> None:
    out_a = tmp_path / "strict_off"
    out_b = tmp_path / "strict_on"
    _run_doctor(out_a, {"TASKX_STRICT": "0", "TASKX_NEON": "0"})
    _run_doctor(out_b, {"TASKX_STRICT": "1", "TASKX_NEON": "0"})
    assert _artifact_hashes(out_a) == _artifact_hashes(out_b)
