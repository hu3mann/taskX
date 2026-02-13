# Router v1 (Assisted)

TaskX Router v1 selects runner/model pairs deterministically and writes handoff artifacts.

## Commands

```bash
taskx route init --repo-root .
taskx route plan --repo-root . --packet PACKET.md
taskx route handoff --repo-root . --packet PACKET.md
taskx route explain --repo-root . --packet PACKET.md --step run-task
```

## Config

`taskx route init` writes:

- `.taskx/runtime/availability.yaml`

## Deterministic Artifacts

- `out/taskx_route/ROUTE_PLAN.json`
- `out/taskx_route/ROUTE_PLAN.md`
- `out/taskx_route/HANDOFF.md`

## Refusal Contract

Planner exits with code `2` when:

- required runner/model pairs are unavailable
- top score is below threshold

In refusal mode, plan artifacts are still written with:

- `status: refused`
- refusal reasons
- top candidates per step

## Safety

- Assisted only (no external runner execution)
- deterministic scoring and serialized outputs
