# Kernel Principles

TaskX operates as a constrained kernel, not an improvisational assistant.

## Principles

1. Packet is law.
2. One Path in auto mode; no hidden fallback routes.
3. Refusal is required when constraints are violated.
4. Artifacts are the execution record.
5. Determinism is mandatory for repeatable runs.
6. Version pinning defines behavioral identity.

## Practical interpretation

- A valid Packet plus declared inputs either yields deterministic Artifacts or a deterministic Refusal.
- If a command, diff, or verification output is missing, the claim is incomplete.
- Version changes are explicit compatibility events, not silent behavior drift.

## Design consequence

TaskX prefers a hard no with evidence over a soft maybe without guarantees.
