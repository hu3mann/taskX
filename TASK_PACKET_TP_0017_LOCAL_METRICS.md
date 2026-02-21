# TASK_PACKET TP_0017 — Telemetry-Free Opt-In Local Metrics

## GOAL
Add local-only, telemetry-free, opt-in usage stats to TaskX CLI, off by default, with explicit visibility and reset controls.

## SCOPE (ALLOWLIST)
- `src/taskx/metrics.py`
- `src/taskx/cli.py`
- `tests/unit/taskx/test_metrics_cli.py`
- `tests/unit/taskx/test_metrics_artifact_invariance.py`

## NON-NEGOTIABLES
- No network calls or remote telemetry.
- Metrics must be disabled by default.
- Metrics must never influence planner, router, artifact writer, or deterministic outputs.
- Keep changes localized and minimal.

## REQUIRED CHANGES
1. Add `src/taskx/metrics.py` with local state file handling.
2. Add `taskx metrics status|enable|disable|show|reset` commands.
3. Wire invocation counting at CLI entry, gated by `TASKX_METRICS=1` and persistent opt-in flag.
4. Add tests proving metrics do not alter artifact hashes for deterministic route planning.

## VERIFICATION COMMANDS
```bash
uv run ruff check src/taskx tests/unit/taskx/test_metrics_cli.py tests/unit/taskx/test_metrics_artifact_invariance.py
uv run mypy src/taskx
uv run pytest tests/unit/taskx/test_metrics_cli.py tests/unit/taskx/test_metrics_artifact_invariance.py
uv run pytest
TASKX_METRICS=1 uv run taskx --help >/dev/null
TASKX_METRICS=1 uv run taskx metrics show
```

## DEFINITION OF DONE
- All verification commands pass.
- Metrics are local-only and opt-in.
- Metrics commands function as specified.
- Deterministic artifact output remains unchanged with metrics on vs off.

## SOURCES
- `src/taskx/cli.py`
- `tests/unit/taskx/test_router_plan_determinism.py`
- `tests/unit/taskx/route_test_utils.py`
