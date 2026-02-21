# Task Packet Format

This document defines what "Task Packet" means for TaskX and what the parser enforces.

## Header

The first line must be an H1 of the form:

```text
# TASK_PACKET TP_#### — Title
```

Where:

- `TP_####` is exactly four digits.
- The separator is an em dash in the spec text; the parser matches a literal " — " sequence.

## Required sections

Task Packets are parsed as `##` headings. The following sections are required:

- `GOAL`
- `SCOPE (ALLOWLIST)`
- `NON-NEGOTIABLES`
- `REQUIRED CHANGES`
- `VERIFICATION COMMANDS`
- `DEFINITION OF DONE`
- `SOURCES`

If any section is missing, parsing fails.

## Allowlist rules

The allowlist is extracted from `SCOPE (ALLOWLIST)` as a markdown bullet list.

- Only bullet items are considered.
- Backticks around paths are allowed.
- The allowlist must be non-empty.

## Verification commands rules

`VERIFICATION COMMANDS` must contain at least one command, extracted from:

1. A fenced code block (preferred), or
2. A bullet list

If no commands are found, parsing fails.

## Project identity (optional)

If a packet includes a `PROJECT IDENTITY` section, it is parsed for key/value items.
Some repositories may require this header (see project identity rails).

## Compatibility and versioning policy

- Additive changes to the packet format should be backward-compatible.
- Contract-breaking changes require a major version bump of TaskX.

## Git Workflow

Task Packet execution must use the dedicated TP git workflow commands:

1. `taskx tp git doctor`
2. `taskx tp git start <TP_ID> <slug>`
3. Implement in `.worktrees/<TP_ID>`
4. `taskx tp git pr <TP_ID> --title "..."`
5. `taskx tp git merge <TP_ID>`
6. `taskx tp git sync-main`
7. `taskx tp git cleanup <TP_ID>`
