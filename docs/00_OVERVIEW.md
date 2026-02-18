# Overview

TaskX is a deterministic execution kernel for task packets.

It is artifact-first and refusal-first:

- If it cannot proceed under declared policy, it refuses with evidence.
- If it did not write an artifact, it did not happen.

## Kernel vs ecosystem

The kernel:

- Validates inputs (task packets and declared config).
- Produces a deterministic plan or a deterministic refusal.
- Executes exactly one selected path in `auto` mode (or emits a handoff in `manual` mode).
- Writes canonical artifacts before exit.

The ecosystem may add scheduling, orchestration, UI, or memory. Those are intentionally out of scope for the kernel.

## Promises

- Deterministic planning and artifact writing for identical inputs and version.
- Stable refusal semantics with evidence.
- No hidden retries or fallback execution paths.

## Non-goals

- Being a general-purpose workflow engine.
- Implicit network access.
- Cross-run mutable state.

## Next

- Architecture: `10_ARCHITECTURE.md`
- Public contract: `11_PUBLIC_CONTRACT.md`
- Install: `01_INSTALL.md`
- Quickstart: `02_QUICKSTART.md`

