# Public Contract

This document defines TaskX's public, user-visible contract: inputs, outputs, determinism, exit codes, and non-goals.

## Inputs

- Task Packet: see `13_TASK_PACKET_FORMAT.md`
- Route availability config: `.taskx/runtime/availability.yaml`

## Outputs

TaskX writes deterministic artifacts for a given invocation:

- Route plan artifacts under `out/taskx_route/`
- Refusal reasons when refusing

Console output is informational. Artifacts are the record.

## Determinism rules

For identical:

- Packet
- Declared inputs
- TaskX version

Outputs must be byte-stable unless explicitly documented otherwise.

## Exit codes

- `0`: success
- `2`: refusal (contractual non-execution)
- `1`: error (unexpected failure)

## Non-goals

- Implicit retries and fallback runners
- Undeclared network access
- Cross-run mutable state

## Versioning policy

TaskX follows Semantic Versioning.

- Patch: bug fixes only
- Minor: additive and backward-compatible
- Major: contract-breaking

