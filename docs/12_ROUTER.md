# Router

TaskX Router v1 selects runner/model pairs deterministically and writes route artifacts.

See `10_ARCHITECTURE.md` for kernel principles.

## Flow

```mermaid
flowchart TD
  A["Packet (PACKET.md)"] --> B["Validation"]
  B --> C["Load availability.yaml"]
  C --> D["Plan steps (order-preserving)"]
  D --> E{"Refuse?"}
  E -- "yes" --> F["Write ROUTE_PLAN.json/.md (status=refused)"]
  E -- "no" --> G["Write ROUTE_PLAN.json/.md (status=planned)"]
  G --> H["Emit HANDOFF.md when needed"]
```

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

## Deterministic artifacts

- `out/taskx_route/ROUTE_PLAN.json`
- `out/taskx_route/ROUTE_PLAN.md`
- `out/taskx_route/HANDOFF.md`

## Refusal conditions and artifacts

Planner exits with code `2` when:

- required runner/model pairs are unavailable
- top score is below threshold

In refusal mode, plan artifacts are still written with:

- `status: refused`
- refusal reasons
- top candidates per step

