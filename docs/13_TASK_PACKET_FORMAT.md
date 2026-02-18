# Task Packet Format

This document defines what "packet" means for TaskX.

## Schema versioning

- Packets are versioned by an explicit schema version field when present.
- Backward-compatible additions are allowed in minor versions.
- Contract-breaking changes require a major version bump.

## Required vs optional fields

At minimum, a packet must provide:

- A stable identity (or a stable file path used as identity)
- Declared steps in an explicit order (when applicable)
- Declared execution mode (`auto` or `manual`) when applicable

Optional fields include:

- Routing hints
- Policy overrides (explicitly declared)

## Examples

Minimal router packet:

```markdown
# Packet
ROUTER_HINTS:
  risk: low
```

Refusal example (missing availability config):

- `taskx route plan` refuses with exit code `2` and writes refusal reasons into route plan artifacts.

