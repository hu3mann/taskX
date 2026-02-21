"""Unit tests for taskx tp git doctor guard behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskx.ops.tp_git.exec import ExecResult
from taskx.ops.tp_git.guards import run_doctor


class _GitStub:
    def __init__(self, outputs: dict[tuple[str, ...], ExecResult]):
        self.outputs = outputs

    def __call__(self, args: list[str], *, repo_root: Path, check: bool = True) -> ExecResult:
        _ = (repo_root, check)
        key = tuple(args)
        if key not in self.outputs:
            raise AssertionError(f"missing stub for args: {args}")
        return self.outputs[key]


def _result(args: list[str], stdout: str = "", stderr: str = "", code: int = 0) -> ExecResult:
    return ExecResult(argv=tuple(["git", *args]), cwd=Path("/repo"), returncode=code, stdout=stdout, stderr=stderr)


def test_doctor_passes_when_main_clean_no_stash(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = {
        ("rev-parse", "--show-toplevel"): _result(["rev-parse", "--show-toplevel"], stdout="/repo\n"),
        ("rev-parse", "--abbrev-ref", "HEAD"): _result(["rev-parse", "--abbrev-ref", "HEAD"], stdout="main\n"),
        ("status", "--porcelain"): _result(["status", "--porcelain"], stdout=""),
        ("stash", "list"): _result(["stash", "list"], stdout=""),
        ("fetch", "--all", "--prune"): _result(["fetch", "--all", "--prune"], stdout=""),
        ("pull", "--ff-only"): _result(["pull", "--ff-only"], stdout="Already up to date.\n"),
    }
    monkeypatch.setattr("taskx.ops.tp_git.guards.run_git", _GitStub(outputs))

    report = run_doctor(repo=Path("/repo"))
    assert report.branch == "main"
    assert report.repo_root == Path("/repo")


def test_doctor_refuses_non_main(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = {
        ("rev-parse", "--show-toplevel"): _result(["rev-parse", "--show-toplevel"], stdout="/repo\n"),
        ("rev-parse", "--abbrev-ref", "HEAD"): _result(["rev-parse", "--abbrev-ref", "HEAD"], stdout="feature\n"),
    }
    monkeypatch.setattr("taskx.ops.tp_git.guards.run_git", _GitStub(outputs))

    with pytest.raises(RuntimeError, match="expected branch main"):
        _ = run_doctor(repo=Path("/repo"))


def test_doctor_refuses_dirty(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = {
        ("rev-parse", "--show-toplevel"): _result(["rev-parse", "--show-toplevel"], stdout="/repo\n"),
        ("rev-parse", "--abbrev-ref", "HEAD"): _result(["rev-parse", "--abbrev-ref", "HEAD"], stdout="main\n"),
        ("status", "--porcelain"): _result(["status", "--porcelain"], stdout=" M file.py\n"),
    }
    monkeypatch.setattr("taskx.ops.tp_git.guards.run_git", _GitStub(outputs))

    with pytest.raises(RuntimeError, match="main has uncommitted changes"):
        _ = run_doctor(repo=Path("/repo"))


def test_doctor_refuses_stash(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = {
        ("rev-parse", "--show-toplevel"): _result(["rev-parse", "--show-toplevel"], stdout="/repo\n"),
        ("rev-parse", "--abbrev-ref", "HEAD"): _result(["rev-parse", "--abbrev-ref", "HEAD"], stdout="main\n"),
        ("status", "--porcelain"): _result(["status", "--porcelain"], stdout=""),
        ("stash", "list"): _result(["stash", "list"], stdout="stash@{0}: WIP\n"),
    }
    monkeypatch.setattr("taskx.ops.tp_git.guards.run_git", _GitStub(outputs))

    with pytest.raises(RuntimeError, match="stash list is non-empty"):
        _ = run_doctor(repo=Path("/repo"))
