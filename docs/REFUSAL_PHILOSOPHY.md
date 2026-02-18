# Refusal Philosophy

TaskX does not treat refusal as a failure mode. It treats refusal as an integrity boundary.

## Why refuse

When required evidence is missing, scope is violated, or policy constraints are incompatible, TaskX must refuse to continue.

Proceeding anyway would break deterministic guarantees and dilute operator trust.

## Integrity over convenience

A refusal preserves auditability:

- the system states what is blocked
- the system states why it is blocked
- the system defines the smallest change needed to proceed

This behavior protects the guarantee that artifacts are authoritative.

## Trust model

Users can trust successful outputs because the same kernel is willing to stop when guarantees cannot be preserved.
