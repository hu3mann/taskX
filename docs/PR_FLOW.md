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
  --restore-branch \
  --require-branch-prefix codex/tp-pr-open-branch-guard
```

## Refusal Rails (Exit 2)

Default behavior refuses when:

- working tree is dirty (`--allow-dirty` overrides)
- HEAD is detached (`--allow-detached` overrides)
- current branch equals base branch (`--allow-base-branch` overrides)
- Branch isolation refusal when branch does not start with required prefix (`--allow-branch-prefix-override` overrides)
- remote URL cannot be parsed into `owner/repo` for fallback URL derivation

## PR Creation Behavior

- Pushes current branch to remote (with `-u` when upstream is missing)
- Uses `gh pr create` when `gh` exists
- Falls back to deterministic URL when `gh` is not available:
  - `https://github.com/<owner>/<repo>/pull/new/<branch>`
- Optional `--refresh-llm` runs docs autogen refresh before push/PR and records report paths in PR artifacts.

## Restore Contract

When `--restore-branch` is enabled (default), TaskX restores original branch/HEAD in a finally path, on both success and failure.

Smoke proof requirement for validation:
- start on `main`
- run `taskx pr open` from a different branch context
- verify final branch is still `main`

## Deterministic Artifacts

- `out/taskx_pr/PR_OPEN_REPORT.json`
- `out/taskx_pr/PR_OPEN_REPORT.md`
