# PR Flow v1 (Assisted)

TaskX PR flow opens a pull request with refusal rails and branch restore semantics.

## Command

```bash
taskx pr open \
  --repo-root . \
  --title "feat: ..." \
  --body-file ./out/pr_body.md \
  --base main \
  --remote origin \
  --draft \
  --restore-branch
```

## Refusal Rails (Exit 2)

Default behavior refuses when:

- working tree is dirty (`--allow-dirty` overrides)
- HEAD is detached (`--allow-detached` overrides)
- current branch equals base branch (`--allow-base-branch` overrides)

## PR Creation Behavior

- Pushes current branch to remote (with `-u` when upstream is missing)
- Uses `gh pr create` when `gh` exists
- Falls back to deterministic URL when `gh` is not available:
  - `https://github.com/<owner>/<repo>/pull/new/<branch>`

## Restore Contract

When `--restore-branch` is enabled (default), TaskX restores original branch/HEAD in a finally path, on both success and failure.

## Deterministic Artifacts

- `out/taskx_pr/PR_OPEN_REPORT.json`
- `out/taskx_pr/PR_OPEN_REPORT.md`
