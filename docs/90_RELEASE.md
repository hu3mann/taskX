# Release (Maintainers)

This document describes how maintainers cut a release using uv.

## Checklist

1. Bump version
2. Tag release
3. Build
4. Publish

## uv-native workflow

```bash
uv lock
uv sync
uv run pytest
uv build
uv publish
```

CI release triggers are tag-based. See your repository workflows for details.
