# TaskX Installation Guide

## Install TaskX into Another Repository

TaskX provides a simple, pinned installation mechanism for consumer repositories (like Dopemux, ChatX, etc.) without vendoring source code.

### Quick Start

**1. Create a pin file in your repository root:**

```bash
cat > .taskx-pin <<'EOF'
install=git
repo=https://github.com/YOUR-USERNAME/taskX.git
ref=v0.1.0
EOF
```

**2. Run the installer:**

```bash
bash /path/to/taskX/scripts/taskx_install_into_repo.sh
```

**3. Verify installation:**

```bash
source .venv/bin/activate  # or .taskx_venv/bin/activate
python -c "import taskx; print(taskx.__version__)"
taskx doctor --timestamp-mode deterministic
```

### Repo Shell Wiring (`project shell`)

TaskX can bootstrap repo-local shell wiring so `taskx` resolves deterministically inside a repository:

```bash
taskx project shell init --repo-root .
taskx project shell status --repo-root .
```

`init` creates (without overwriting existing files):
- `.envrc` with `export PATH="$(pwd)/scripts:$PATH"`
- `scripts/taskx` shim
- `scripts/taskx-local` launcher

Reports are written to:
- `out/taskx_project_shell/PROJECT_SHELL_REPORT.json`
- `out/taskx_project_shell/PROJECT_SHELL_REPORT.md`

If `.envrc` exists but `direnv` is missing, `taskx doctor` emits a warning (non-failing).

### One-Command Repo Stabilization (`project upgrade`)

TaskX can run shell wiring, instruction pack repair, and doctor checks in one deterministic command:

```bash
taskx project upgrade --repo-root . --allow-init-rails
```

Default behavior:
- Validates identity rails (`.taskxroot`, `.taskx/project.json`)
- Runs `project shell init`
- Runs `project doctor --fix --mode both` on `.taskx/instructions`
- Runs `taskx doctor`

Reports are written to:
- `out/taskx_project_upgrade/PROJECT_UPGRADE_REPORT.json`
- `out/taskx_project_upgrade/PROJECT_UPGRADE_REPORT.md`

### Dev Note: Multiple TaskX Installs

If `taskx` on `PATH` points to a different install than this checkout, run commands from this repo with:

```bash
PYTHONPATH=src python -m taskx ...
```

Or install editable in your active environment:

```bash
pip install -e .
```

### Hard Repo Marker Requirement

Stateful TaskX commands now fail closed unless the current repository has a `.taskxroot` file at its root.

- Required for guarded/stateful commands: `.taskxroot`
- Not accepted for guarded/stateful commands: `pyproject.toml` fallback
- `pyproject.toml` project-name fallback remains for non-stateful discovery commands such as doctor/info flows

If a guarded command is run in a non-TaskX repository, TaskX refuses execution and prints both the detected repo root and current working directory.

### How to Generate a Rescue Patch

When a guarded command is blocked because `.taskxroot` is missing, you can ask TaskX to preserve your current WIP diff before exit:

```bash
taskx gate-allowlist --run /path/to/run --rescue-patch auto
```

`--rescue-patch auto` writes to:

```text
<cwd>/out/taskx_rescue/<timestamp>/rescue.patch
```

You can also provide an explicit output path:

```bash
taskx gate-allowlist --run /path/to/run --rescue-patch /tmp/my_rescue.patch
```

Rescue patch contents are limited to:

- `git status --porcelain`
- `git diff`

### Why This Protects WIP

The hard `.taskxroot` requirement prevents accidental stateful TaskX runs in lookalike repositories.  
If you still invoke a guarded command in the wrong project, rescue patch mode snapshots your uncommitted git state before TaskX exits, so you can recover edits safely without continuing the blocked command.

### Pin File Format

The `.taskx-pin` file defines which TaskX version to install. Place it at your repository root.

#### Option 1: Git Tag (Recommended)

Install from a specific git tag:

```
install=git
repo=https://github.com/YOUR-USERNAME/taskX.git
ref=v0.1.0
```

**Fields:**
- `install=git` - Use git installation method
- `repo=<url>` - Git repository URL (HTTPS or SSH)
- `ref=<ref>` - Git reference (tag, branch, or commit SHA)

**Recommended:** Use version tags (e.g., `v0.1.0`) for reproducible installs.

#### Option 2: Local Wheel

Install from a local wheel file:

```
install=wheel
path=dist/taskx-0.1.0-py3-none-any.whl
```

**Fields:**
- `install=wheel` - Use wheel installation method
- `path=<path>` - Path to wheel file (absolute or relative to repo root)

**Use case:** Offline installations or air-gapped environments.

### Installer Script

The installer script (`scripts/taskx_install_into_repo.sh`) performs these steps:

1. **Find repository root** - Walks up to find `.git` or `pyproject.toml`
2. **Read `.taskx-pin`** - Parses configuration
3. **Create/use venv** - Uses `.venv` if exists, else creates `.taskx_venv`
4. **Install TaskX** - According to pin configuration
5. **Verify** - Checks version and schema loading

**Location:** The installer must be run from the TaskX repository:
```bash
bash ~/code/taskX/scripts/taskx_install_into_repo.sh
```

**From consumer repo:** Run from any directory within the consumer repository.

### Pin Audit Tool

Validate your `.taskx-pin` configuration:

```bash
python ~/code/taskX/scripts/taskx_pin_audit.py
```

**Output:**
```
TaskX Pin Configuration Summary
==================================================
Repository root: /Users/you/code/your-repo

Install method: git
Repository: https://github.com/YOUR-USERNAME/taskX.git
Reference: v0.1.0
Install target: git+https://github.com/YOUR-USERNAME/taskX.git@v0.1.0

Status: ✅ Configuration valid
```

**Exit codes:**
- `0` - Configuration valid
- `1` - Configuration invalid or missing

### Virtual Environment

The installer creates or uses a virtual environment:

**Priority:**
1. If `.venv` exists → use it
2. Otherwise → create `.taskx_venv`

**Activate:**
```bash
source .venv/bin/activate
# or
source .taskx_venv/bin/activate
```

### Pin Strategies

#### Production (Strict Pinning)

```
install=git
repo=https://github.com/YOUR-USERNAME/taskX.git
ref=v0.1.0
```

**Pros:** Guaranteed reproducibility
**Cons:** Manual upgrade process

#### Development (Branch Pinning)

```
install=git
repo=https://github.com/YOUR-USERNAME/taskX.git
ref=main
```

**Pros:** Always latest features
**Cons:** May break unexpectedly

**Recommended:** Use tags for production, branches for development.

### Upgrading TaskX

**1. Update `.taskx-pin`:**

```bash
vim .taskx-pin
# Change: ref=v0.1.0
# To:     ref=v0.2.0
```

**2. Reinstall:**

```bash
bash ~/code/taskX/scripts/taskx_install_into_repo.sh
```

**3. Verify:**

```bash
source .venv/bin/activate
python -c "import taskx; print(taskx.__version__)"
```

### Examples

#### Example 1: Install in Dopemux

```bash
cd ~/code/dopemux-mvp

# Create pin file
cat > .taskx-pin <<'EOF'
install=git
repo=https://github.com/YOUR-USERNAME/taskX.git
ref=v0.1.0
EOF

# Install
bash ~/code/taskX/scripts/taskx_install_into_repo.sh

# Verify
source .venv/bin/activate
taskx doctor --timestamp-mode deterministic
```

#### Example 2: Install in ChatX

```bash
cd ~/code/ChatRipperXXX

# Create pin file
cat > .taskx-pin <<'EOF'
install=git
repo=https://github.com/YOUR-USERNAME/taskX.git
ref=v0.1.0
EOF

# Install
bash ~/code/taskX/scripts/taskx_install_into_repo.sh

# Verify
source .taskx_venv/bin/activate
taskx --version
```

#### Example 3: Offline Install with Wheel

```bash
cd ~/code/your-repo

# Create pin file pointing to wheel
cat > .taskx-pin <<'EOF'
install=wheel
path=/path/to/taskx-0.1.0-py3-none-any.whl
EOF

# Install
bash ~/code/taskX/scripts/taskx_install_into_repo.sh

# Verify
source .taskx_venv/bin/activate
taskx doctor
```

### Troubleshooting

#### Pin file not found

**Error:**
```
[ERROR] .taskx-pin file not found
```

**Fix:** Create `.taskx-pin` at repository root:
```bash
cat > .taskx-pin <<'EOF'
install=git
repo=https://github.com/YOUR-USERNAME/taskX.git
ref=v0.1.0
EOF
```

#### Invalid install method

**Error:**
```
[ERROR] Invalid install method: latest
```

**Fix:** Use only `git` or `wheel`:
```
install=git
```

#### Wheel not found

**Error:**
```
[ERROR] Wheel file not found: dist/taskx-0.1.0.whl
```

**Fix:** Use absolute path or verify relative path from repo root:
```
path=/absolute/path/to/taskx-0.1.0-py3-none-any.whl
```

#### Git reference not found

**Error:**
```
ERROR: Could not find a version that satisfies the requirement
```

**Fix:** Verify the git reference exists:
```bash
git ls-remote https://github.com/YOUR-USERNAME/taskX.git
```

### Best Practices

**1. Use version tags for production:**
```
ref=v0.1.0
```

**2. Commit `.taskx-pin` to version control:**
```bash
git add .taskx-pin
git commit -m "chore: pin TaskX to v0.1.0"
```

**3. Add venv to `.gitignore`:**
```bash
echo ".taskx_venv/" >> .gitignore
```

**4. Verify after installation:**
```bash
taskx doctor --timestamp-mode deterministic
```

**5. Audit pin configuration:**
```bash
python ~/code/taskX/scripts/taskx_pin_audit.py
```

### Manifests & Replay

TaskX supports per-run audit manifests for deterministic replay checks.

**Initialize at run start:**

```bash
taskx manifest init \
  --run /tmp/taskx_runs/RUN_DETERMINISTIC \
  --task-packet TASKX_A24 \
  --mode ACT \
  --timestamp-mode deterministic
```

**Run stateful gates with manifest recording enabled (optional auto-init):**

```bash
taskx gate-allowlist --run /tmp/taskx_runs/RUN_DETERMINISTIC --manifest --timestamp-mode deterministic
taskx promote-run --run /tmp/taskx_runs/RUN_DETERMINISTIC --manifest --timestamp-mode deterministic
taskx ci-gate --run /tmp/taskx_runs/RUN_DETERMINISTIC --manifest --timestamp-mode deterministic
taskx commit-run --run /tmp/taskx_runs/RUN_DETERMINISTIC --manifest --timestamp-mode deterministic
```

Each command appends a command record to `TASK_PACKET_MANIFEST.json` and writes output logs to `_manifest_logs/`.

**Run replay check at end:**

```bash
taskx manifest check --run /tmp/taskx_runs/RUN_DETERMINISTIC
```

Replay check compares `artifacts_expected` against files currently present and reports:
- Missing artifacts (expected but absent)
- Extra artifacts (present but not expected)

**Recommended ops flow:**
1. Initialize run workspace.
2. Initialize manifest (`taskx manifest init`).
3. Execute stateful gates with `--manifest`.
4. Run `taskx manifest check` before promotion/rollout decisions.

### Integration with CI/CD

## Stateful Run Directory Layout

TaskX stateful commands now follow a canonical run directory layout:

```text
<run_root>/<run_id>/
```

### Run Root Selection (Precedence)

1. `--run-root <path>`
2. `TASKX_RUN_ROOT` environment variable
3. If running inside a TaskX repo: `<repo_root>/out/runs`
4. Fallback: `<cwd>/out/runs`

### Run ID Rules

- Deterministic mode: `RUN_DETERMINISTIC`
- Timestamped mode (`now` or `wallclock`): `RUN_YYYYMMDD_HHMMSS`

This keeps deterministic runs stable and avoids timestamped paths unless explicitly requested.

### Standard Artifact Filenames

Stateful commands only write artifacts inside the selected run directory and use these canonical names:

- `RUN_ENVELOPE.json`
- `EVIDENCE.md`
- `ALLOWLIST_DIFF.json`
- `VIOLATIONS.md`
- `PROMOTION_TOKEN.json` (legacy `PROMOTION.json` may still be present for compatibility)
- `COMMIT_RUN.json`
- `DOCTOR_REPORT.json` (when doctor is run with `--out <run_dir>`)

Only artifacts for executed commands are created.

### Recommended Ops Structure

```text
out/runs/
  RUN_DETERMINISTIC/
    RUN_ENVELOPE.json
    EVIDENCE.md
    ALLOWLIST_DIFF.json
    VIOLATIONS.md
    PROMOTION_TOKEN.json
    COMMIT_RUN.json
```

**GitHub Actions example:**

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Clone TaskX
        run: git clone https://github.com/YOUR-USERNAME/taskX.git /tmp/taskX

      - name: Install TaskX
        run: bash /tmp/taskX/scripts/taskx_install_into_repo.sh

      - name: Verify TaskX
        run: |
          source .venv/bin/activate
          taskx doctor --timestamp-mode deterministic

      - name: Use TaskX
        run: |
          source .venv/bin/activate
          taskx compile-tasks --mode mvp
```

### No Vendoring Policy

TaskX is designed to be installed as a dependency, **not vendored**:

- ❌ Don't copy TaskX source files into your repo
- ❌ Don't include TaskX as a git submodule
- ✅ Do use `.taskx-pin` + installer script
- ✅ Do pin to specific versions for reproducibility

### See Also

- **Installer script:** `scripts/taskx_install_into_repo.sh`
- **Audit tool:** `scripts/taskx_pin_audit.py`
- **TaskX documentation:** `README.md`
