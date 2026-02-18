# Install

This is the single source of truth for installation.

## End users (pip)

```bash
python -m pip install taskx
```

## Developers (uv-first)

```bash
uv lock
uv sync
uv run taskx --help
```

### Running tests

```bash
uv run pytest
```

### Editable install (optional)

```bash
python -m pip install -e ".[dev]"
```

