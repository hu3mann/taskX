# Overview

TaskX is a deterministic execution kernel for task packets.

## What it is

TaskX enforces a narrow contract:

- determinism for planning and execution artifacts
- refusal when policy, scope, or evidence constraints are violated
- artifacts as the source of truth for what happened
- one path in auto mode, or an explicit handoff in manual mode

## What it is not

TaskX is not a generic orchestration platform. It does not provide hidden retries, implicit fallbacks, or background side effects.

## Kernel boundary

The kernel validates inputs, selects one deterministic route, executes that route, and exits after writing canonical artifacts.

Scheduling, memory, UX layers, and long-running orchestration belong to external systems.

## Operating promise

Given the same packet, declared inputs, and TaskX version, output artifacts and refusal behavior are stable.

## Next docs

- `10_ARCHITECTURE.md`
- `11_PUBLIC_CONTRACT.md`
- `13_TASK_PACKET_FORMAT.md`
- `20_WORKTREES_COMMIT_SEQUENCING.md`
