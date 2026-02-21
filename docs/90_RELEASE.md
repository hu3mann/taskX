# Release Process (Maintainers)

This guide details the release process for TaskX maintainers.

## Release Process

1. Bump version in `pyproject.toml`
2. Commit
3. Tag: `git tag vX.Y.Z`
4. Push tag
5. CI builds + publishes

## Release checklist

1. Update version
2. Changelog
3. Verify
4. Tag
5. Publish

## Preparing the release

### Bump version

Update the version string in two locations:

1. `src/taskx/__init__.py`
2. `pyproject.toml`

Commit these changes:

```bash
git add src/taskx/__init__.py pyproject.toml
git commit -m "chore: bump version to X.Y.Z"
```

### Verify locally

Run tests:

```bash
uv run pytest
```

Build artifacts:

```bash
uv build
```

Publish:

```bash
uv publish
```

If your repo uses a local release verification script, run it before tagging.

## Tagging and publishing

Create a tag matching your version (must start with `v`):

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Pushing a tag should trigger the release workflow in CI.

## Automated workflow

After pushing the tag, your GitHub Actions release workflow should:

1. Verify tag matches `pyproject.toml` version
2. Run tests in a clean environment
3. Build sdist and wheel
4. Smoke test install and `taskx --help`
5. Publish artifacts

## Security & Provenance Gates

1. Dependency scan must pass (`pip-audit --strict`) in CI.
2. Release artifact provenance attestation is generated in CI.
3. Container provenance attestation is generated in CI.
4. Release remains tag-gated and fails on tag/version mismatch.
