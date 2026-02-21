"""Unit tests for taskx tp git naming helpers."""

from __future__ import annotations

from pathlib import Path

from taskx.ops.tp_git.naming import build_tp_branch, build_worktree_path, normalize_slug


def test_normalize_slug_basic() -> None:
    assert normalize_slug("Workflow") == "workflow"
    assert normalize_slug("my new TASK") == "my-new-task"


def test_normalize_slug_strips_invalid_and_collapses_dashes() -> None:
    assert normalize_slug("A__B!!C") == "a-b-c"
    assert normalize_slug("---x---y---") == "x-y"


def test_normalize_slug_fallback() -> None:
    assert normalize_slug("@@@") == "task"
    assert normalize_slug("   ") == "task"


def test_build_tp_branch() -> None:
    assert build_tp_branch("TP-GIT-0001", "My Workflow") == "tp/TP-GIT-0001-my-workflow"


def test_build_worktree_path() -> None:
    root = Path("/tmp/repo")
    expected = (root / ".worktrees" / "TP-GIT-0001").resolve()
    assert build_worktree_path(root, "TP-GIT-0001") == expected
