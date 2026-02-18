# Quickstart

## 60-second route plan

1. Initialize routing availability for this repo:

```bash
taskx route init --repo-root .
```

2. Create a minimal packet file:

```markdown
# TASK_PACKET TP_0001 — Example minimal packet

## GOAL
Summarize the current routing setup.

## SCOPE (ALLOWLIST)
- docs/**
- src/**

## ROUTER_HINTS
risk: low
```

3. Produce deterministic route plan artifacts:

```bash
taskx route plan --repo-root . --packet PACKET.md
```

## Expected artifacts

Route plan output is written under:

- `out/taskx_route/ROUTE_PLAN.json`
- `out/taskx_route/ROUTE_PLAN.md`
- `out/taskx_route/HANDOFF.md` (for handoff flows)

## Refusal example

If required configuration is missing, TaskX refuses with evidence and a stable exit code.

Example: running `taskx route plan` without initializing availability will refuse and still write plan artifacts with refusal reasons.

See `13_TASK_PACKET_FORMAT.md` for packet requirements.

