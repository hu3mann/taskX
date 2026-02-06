# Release Process

This guide details the release process for TaskX maintainers. We use a semi-automated workflow to ensure every release is verified, tested, and reliable.

## 📋 Release Checklist

1. [ ] **Update Version**: Bump version numbers in code.
2. [ ] **Changelog**: Document new features and fixes.
3. [ ] **Verify**: Run the local release script.
4. [ ] **Tag**: Push the git tag.
5. [ ] **Publish**: Let GitHub Actions handle the rest.

---

## 🚀 1. Preparing the Release

### Bump Version
Update the version string in **two** locations:

**1. `src/taskx/__init__.py`**
```python
__version__ = "0.2.0"
```

**2. `pyproject.toml`**
```toml
[project]
version = "0.2.0"
```

Commit these changes:
```bash
git add src/taskx/__init__.py pyproject.toml
git commit -m "chore: bump version to 0.2.0"
```

### Run Verification Script
We provide a local script to simulate the release process before you push. This catches issues early.

```bash
bash scripts/taskx_release_local.sh
```

**What this does:**
- ✅ **Cleanliness**: Ensures git working tree is clean.
- ✅ **Tests**: Runs full `pytest` suite.
- ✅ **Build**: Compiles source distribution (`.tar.gz`) and wheel (`.whl`).
- ✅ **Install**: Verifies the wheel installs correctly in a fresh, isolated virtual environment.

> **Note:** Do not proceed if this script fails.

---

## 🏷 2. Tagging & Publishing

Once the verification script passes, you are ready to ship.

### Create Tag
Create a git tag matching your version number (must start with `v`).

```bash
git tag v0.2.0
```

### Push to GitHub
Pushing the tag triggers the automated release workflow.

```bash
git push origin v0.2.0
```

---

## 🤖 3. Automated Workflow

After pushing the tag, the **[GitHub Actions Release Workflow](../.github/workflows/taskx_release.yml)** takes over.

### It performs these steps:
1. **Consistency Check**: Verifies tag matches `pyproject.toml` version.
2. **Test Suite**: Runs tests again in a clean CI environment.
3. **Build**: Generates production artifacts.
4. **Smoke Test**: Installs artifacts and runs `taskx doctor`.
5. **Release**: Creates a draft release on GitHub with attached artifacts.

### Verify
Visit the [Releases Page](https://github.com/OWNER/REPO/releases) to confirm:
- Release `v0.2.0` exists.
- `taskx-0.2.0-py3-none-any.whl` is attached.
- `taskx-0.2.0.tar.gz` is attached.

---

## ⚠️ Troubleshooting

### Local Script Fails
- **Dir not clean?** Commit or stash your changes.
- **Tests failed?** Fix the bugs first!
- **Clean venv failed?** Check that your `pyproject.toml` includes all required schema files.

### CI Workflow Fails
- **Version Mismatch:** Did you forget to bump `pyproject.toml`? Delete the remote tag, fix it, and re-tag.
  ```bash
  git tag -d v0.2.0
  git push origin :refs/tags/v0.2.0
  ```

### Missing Schemas in Wheel
If `taskx doctor` complains about missing schemas after install:
- Ensure `MANIFEST.in` (or hatch config) includes the `taskx_schemas` directory.
- Verify `taskx_schemas/__init__.py` exists.
