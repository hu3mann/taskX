# TaskX Installation Guide

## Install TaskX into Another Repository

TaskX provides a simple, pinned installation mechanism for consumer repositories (like Dopemux, ChatX, etc.) without vendoring source code.

### Quick Start (Automatic)

The easiest way to install TaskX into your repository is using the unified installer script. This will set up a virtual environment and install TaskX.

**1. One-Liner Install:**

Run this from your repository root:

```bash
curl -fsSL https://raw.githubusercontent.com/hu3mann/taskX/main/scripts/install.sh | bash
```

This will:
- Detect your repository root.
- Create a `.taskx-pin` file (defaulting to the latest `main` version) if one doesn't exist.
- Create a virtual environment (`.taskx_venv` or reuse `.venv`).
- Install TaskX.

**2. Verify installation:**

```bash
source .taskx_venv/bin/activate  # or .venv/bin/activate
taskx doctor --timestamp-mode deterministic
```

### Advanced Installation

You can customize the installation by providing arguments to the script or creating a `.taskx-pin` file manually.

**Install a specific version:**

```bash
curl -fsSL https://raw.githubusercontent.com/hu3mann/taskX/main/scripts/install.sh | bash -s -- --version v0.2.0
```

**Manual Pin Configuration:**

Create `.taskx-pin` before running the installer:

```bash
cat > .taskx-pin <<'EOF'
install=git
repo=https://github.com/hu3mann/taskX.git
ref=v0.1.0
EOF

curl -fsSL https://raw.githubusercontent.com/hu3mann/taskX/main/scripts/install.sh | bash
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

### Upgrading TaskX

TaskX now includes a self-upgrade command.

**Upgrade to the latest version:**

```bash
taskx upgrade --latest
```

**Upgrade/Downgrade to a specific version:**

```bash
taskx upgrade --version v0.2.0
```

These commands will automatically update your `.taskx-pin` file and reinstall the package.

### Pin File Format

The `.taskx-pin` file defines which TaskX version to install. Place it at your repository root.

#### Option 1: Git Tag (Recommended)

Install from a specific git tag:

```
install=git
repo=https://github.com/hu3mann/taskX.git
ref=v0.1.0
```

#### Option 2: Local Wheel

Install from a local wheel file:

```
install=wheel
path=dist/taskx-0.1.0-py3-none-any.whl
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
