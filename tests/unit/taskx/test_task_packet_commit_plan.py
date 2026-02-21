"""Tests for optional COMMIT PLAN parsing in task packets."""

from __future__ import annotations

from pathlib import Path

import pytest

from taskx.pipeline.task_runner.parser import parse_task_packet


def _write_packet(tmp_path: Path, *, commit_plan_block: str) -> Path:
    packet = tmp_path / "TP_0110_TEST.md"
    packet.write_text(
        f"""# TASK_PACKET TP_0110 — Commit Plan Parsing Test

## GOAL
Test parsing.

## SCOPE (ALLOWLIST)
- src/example.py

## NON-NEGOTIABLES
- Do not break.

## REQUIRED CHANGES
- Add support.

## COMMIT PLAN
{commit_plan_block}

## VERIFICATION COMMANDS
```bash
pytest -q
```

## DEFINITION OF DONE
- Works.

## SOURCES
- src/example.py
""",
        encoding="utf-8",
    )
    return packet


def test_parse_task_packet_commit_plan_happy_path(tmp_path: Path) -> None:
    packet = _write_packet(
        tmp_path,
        commit_plan_block="""```json
{
  "commit_plan": [
    {
      "step_id": "C1",
      "message": "implement parser support",
      "allowlist": ["src/taskx/pipeline/task_runner/parser.py"],
      "verify": ["ruff check .", "pytest -q"]
    },
    {
      "step_id": "C2",
      "message": "wire cli",
      "allowlist": ["src/taskx/cli.py"]
    }
  ]
}
```""",
    )

    info = parse_task_packet(packet)

    assert info.commit_plan is not None
    assert len(info.commit_plan) == 2
    assert info.commit_plan[0].step_id == "C1"
    assert info.commit_plan[0].verify == ["ruff check .", "pytest -q"]
    assert info.commit_plan[1].step_id == "C2"
    assert info.commit_plan[1].verify is None


def test_parse_task_packet_commit_plan_invalid_json(tmp_path: Path) -> None:
    packet = _write_packet(
        tmp_path,
        commit_plan_block="""```json
{ invalid json }
```""",
    )

    with pytest.raises(ValueError, match="invalid COMMIT PLAN JSON"):
        parse_task_packet(packet)


def test_parse_task_packet_commit_plan_missing_required_keys(tmp_path: Path) -> None:
    packet = _write_packet(
        tmp_path,
        commit_plan_block="""```json
{
  "commit_plan": [
    {
      "message": "missing step_id",
      "allowlist": ["src/taskx/cli.py"]
    }
  ]
}
```""",
    )

    with pytest.raises(ValueError, match="empty step_id"):
        parse_task_packet(packet)
