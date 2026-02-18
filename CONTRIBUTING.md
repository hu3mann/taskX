# Contributing

Thank you for contributing to TaskX.

## Development Setup

1. Install `uv`.
2. Sync dependencies:

```bash
uv sync
```

3. Run tests before opening a PR:

```bash
uv run pytest
```

## Pull Request Requirements

Every PR should include a concise Proof Bundle:

- `git status --porcelain`
- `git diff --name-only`
- Relevant command output that validates behavior

Keep changes scoped to the task packet. Avoid unrelated refactors.

## Commit and Review Expectations

- Use clear commit messages.
- Keep commits small and deterministic.
- Include risk notes for behavior changes.
