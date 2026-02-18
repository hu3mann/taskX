# Contributing

## Development Setup

1. Install Python 3.11+ and `uv`.
2. Create and sync dependencies:

```bash
uv sync --all-extras
```

3. Verify CLI:

```bash
uv run taskx --help
```

## Local Validation

Run tests before opening a pull request:

```bash
uv run pytest
```

If you changed CLI behavior, include command examples and expected output in your PR description.

## Commit and PR Guidelines

- Keep commits small and scoped.
- Use conventional commit prefixes (for example: `feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- Include verification evidence for behavior changes.
- Avoid unrelated refactors in the same PR.

## Reporting Issues

Use GitHub issues for bugs and feature requests.
For security reports, follow `SECURITY.md`.
