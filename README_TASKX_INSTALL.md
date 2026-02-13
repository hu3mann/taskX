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

### Assisted Routing (`taskx route`)

TaskX Router v1 is assisted-only. It selects runner/model pairs deterministically and prints handoff instructions; it does not invoke external runners.

```bash
taskx route init --repo-root .
taskx route plan --repo-root . --packet PACKET.md
taskx route handoff --repo-root . --packet PACKET.md
taskx route explain --repo-root . --packet PACKET.md --step run-task
```

Config:
- `.taskx/runtime/availability.yaml`

Deterministic artifacts:
- `out/taskx_route/ROUTE_PLAN.json`
- `out/taskx_route/ROUTE_PLAN.md`
- `out/taskx_route/HANDOFF.md`

Refusal contract:
- exit code `2` for unavailable/low-confidence routes
- writes plan artifacts with `status="refused"` and candidate context

### PR Flow (`taskx pr open`)

TaskX PR flow is assisted-only and branch-safe. It captures current branch/HEAD, runs push + PR creation, then restores original branch/HEAD by default.

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

Default refusal rails (exit code `2`):
- dirty tree unless `--allow-dirty`
- detached HEAD unless `--allow-detached`
- running from base branch unless `--allow-base-branch`
- branch isolation refusal when current branch does not start with required prefix (override with `--allow-branch-prefix-override`)
- remote URL cannot be parsed into `owner/repo` for deterministic fallback URL

Deterministic artifacts:
- `out/taskx_pr/PR_OPEN_REPORT.json`
- `out/taskx_pr/PR_OPEN_REPORT.md`

Optional integration:
- `--refresh-llm` runs `taskx docs refresh-llm` before push/PR and records result in `PR_OPEN_REPORT`.

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

### Virtual Environment

The installer creates or uses a virtual environment:

**Priority:**
1. If `.venv` exists -> use it
2. Otherwise -> create `.taskx_venv`

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
