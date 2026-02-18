# Worktrees + Commit Sequencing (Maintainers)

This document is maintainer-level.

## CLI UX (Final Wording)

TaskX prints an identity banner to stderr at command start:
`[taskx] project=... repo=... branch=... run=...`
Use it as a quick wrong-repo tripwire before you execute worktree actions.
Banner uses ANSI color on TTY. Set `NO_COLOR=1` to disable.

### `taskx wt start`

```bash
taskx wt start --run <RUN_DIR> \
  [--branch <name>] \
  [--base main] \
  [--remote origin] \
  [--worktree-path <path>] \
  [--dirty-policy refuse|stash]
```

Help text:

Create an isolated worktree + task branch for a Task Packet run.
All packet commits must occur inside this worktree.
Refuses to operate on a dirty repository unless `--dirty-policy stash` is provided.

Hard refusals:

- Dirty and `refuse`:

```text
ERROR: repository working tree is dirty.
Run with --dirty-policy stash to stash changes, or clean manually.
```

- Branch exists:

```text
ERROR: branch 'tp/0123-feature' already exists.
Refusing to reuse branch for deterministic execution.
```

### `taskx commit-sequence`

```bash
taskx commit-sequence --run <RUN_DIR> \
  [--allow-unpromoted] \
  [--dirty-policy refuse|stash]
```

Help text:

Execute the COMMIT PLAN defined in the Task Packet.
Creates one commit per step, staging only allowlisted changed files.
Refuses to run on main branch.
Refuses if index contains pre-staged changes.

Hard refusals:

- On `main` branch:

```text
ERROR: commit-sequence cannot run on 'main'.
Use taskx wt start to create a worktree.
```

- Staged changes exist:

```text
ERROR: git index already contains staged files.
Commit-sequence requires a clean index.
```

- Empty step commit:

```text
ERROR: step C3 would create an empty commit.
No allowlisted changed files found.
```

- Dirty outside allowlists with `refuse`:

```text
ERROR: changes detected outside commit plan allowlists.
Use --dirty-policy stash or clean manually.
```

### `taskx finish`

```bash
taskx finish --run <RUN_DIR> \
  [--mode rebase-ff] \
  [--cleanup/--no-cleanup] \
  [--dirty-policy refuse|stash]
```

Defaults:

- `mode = rebase-ff`
- `cleanup = true`
- `dirty-policy = refuse`

Help text:

Finalize a Task Packet run.
Rebases task branch onto `origin/main`, fast-forwards `main`,
pushes to remote, verifies sync, and optionally cleans up.

Hard refusals:

- Rebase conflict:

```text
ERROR: rebase onto origin/main failed.
Resolve conflicts manually and re-run taskx finish.
```

- `main` not fast-forwardable:

```text
ERROR: main is not fast-forwardable.
Repository state diverged.
```

- Push failure:

```text
ERROR: push to origin/main failed.
Local and remote are not synchronized.
```

## `FINISH.json` Schema (v1)

```json
{
  "schema_version": "1.0",
  "mode": "rebase-ff",
  "branch": "tp/0110-worktree-seq",
  "base_branch": "main",
  "remote": "origin",
  "pre_rebase_head": "abc123",
  "post_rebase_head": "def456",
  "main_before_merge": "aaa111",
  "main_after_merge": "bbb222",
  "remote_after_push": "bbb222",
  "cleanup": true,
  "dirty_policy": "refuse",
  "timestamp_utc": "2026-02-11T22:14:01Z"
}
```

Invariant:

`main_after_merge == remote_after_push`

## `DIRTY_STATE.json` Schema (v1)

Append-only list:

```json
[
  {
    "schema_version": "1.0",
    "location": "repo_root|worktree",
    "policy": "stash",
    "stash_ref": "stash@{0}",
    "message": "taskx:wt-start:RUN_0110",
    "status_porcelain": [
      " M src/taskx/cli.py",
      "?? notes.txt"
    ],
    "timestamp_utc": "2026-02-11T21:58:02Z"
  }
]
```

Never auto-pop stash. Determinism > convenience.

## Philosophy

TaskX enforces:

- No direct commits to `main`
- One Task Packet = one contiguous commit chain
- Deterministic, auditable merges
- No silent dirty-state handling

All packet work occurs inside an isolated git worktree.

## Workflow (Solo Default)

```bash
taskx wt start --run out/runs/0123
cd out/worktrees/tp_0123_feature

# implement changes

taskx commit-sequence --run ../../runs/0123

taskx finish --run ../../runs/0123
```

Finish defaults to:

- rebase onto `origin/main`
- fast-forward merge into `main`
- push
- verify
- cleanup

## Dirty Policy

Default:

`--dirty-policy refuse`

Optional:

`--dirty-policy stash`

TaskX will:

- stash with deterministic message
- log stash reference in `DIRTY_STATE.json`
- never auto-pop

## Artifacts

| File | Purpose |
| :--- | :--- |
| `WORKTREE.json` | Worktree metadata |
| `COMMIT_SEQUENCE_RUN.json` | Commit-by-step audit |
| `FINISH.json` | Merge + push audit |
| `DIRTY_STATE.json` | Stash log |

All artifacts are written to the run directory.

## Commit Plan Format

Inside the Task Packet:

````markdown
## COMMIT PLAN
```json
{
  "commit_plan": [
    {
      "step_id": "C1",
      "message": "example step",
      "allowlist": ["src/file.py"],
      "verify": ["ruff check .", "pytest -q"]
    }
  ]
}
```
````

Each step produces exactly one commit.

Empty steps are refused.

## Guarantees

After `taskx finish`:

- `main` contains the full packet commit chain
- `origin/main` matches local `main`
- No merge commits (solo default)
- Worktree removed (unless `--no-cleanup`)
