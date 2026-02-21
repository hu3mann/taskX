# TP Git Workflow

TaskX now provides a fail-closed Task Packet git surface under `taskx tp git`.

## Required flow

1. `taskx tp git doctor`
2. `taskx tp git start <TP_ID> <slug>`
3. Do implementation work in `.worktrees/<TP_ID>`
4. `taskx tp git pr <TP_ID> --title "..." [--body ... | --body-file ...]`
5. `taskx tp git merge <TP_ID>`
6. `taskx tp git sync-main`
7. `taskx tp git cleanup <TP_ID>`

## Command reference

- `taskx tp git doctor [--repo <path>]`
- `taskx tp git start <TP_ID> <slug> [--repo <path>] [--reuse]`
- `taskx tp git status <TP_ID> [--repo <path>]`
- `taskx tp git pr <TP_ID> --title "..." [--body ... | --body-file ...] [--repo <path>]`
- `taskx tp git merge <TP_ID> [--squash|--merge|--rebase] [--repo <path>]`
- `taskx tp git sync-main [--repo <path>]`
- `taskx tp git cleanup <TP_ID> [--repo <path>]`
- `taskx tp git list [--repo <path>]`

## Fail-closed rules

- Doctor refuses when branch is not `main`.
- Doctor refuses when `git status --porcelain` is non-empty.
- Doctor refuses when `git stash list` is non-empty.
- Merge refuses when `gh` auth is missing or auto-merge cannot be enabled.
- Cleanup refuses dirty worktrees.
