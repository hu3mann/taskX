# Project Doctor

The project doctor inspects a repository and reports integrity status. It does not mutate project state.

## PASS/WARN/FAIL semantics

- PASS: exit `0`
- WARN: exit `0` (diagnostic warnings)
- FAIL: non-zero exit (stable)

## What doctor checks

- Project mode and identity rails
- Expected file layout for the selected mode
- Config consistency

## What doctor never does

- It never mutates packet execution behavior.
- It never modifies repository files unless explicitly running a fix mode.

## Operator prompt export policy (Policy A)

Note: `taskx ops doctor` exports the operator prompt by default unless `--no-export` is set.

This export does not affect packet routing or execution behavior. It exists to make operator context observable.

See also:

- Router: `12_ROUTER.md`
- Architecture: `10_ARCHITECTURE.md`
