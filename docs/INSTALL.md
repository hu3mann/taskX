# TaskX Installation & Setup

TaskX is designed for deterministic, offline-first development. Whether you're a solo developer or part of a large organization, we support multiple installation methods to fit your workflow.

## 🚀 Quick Start

### The "Just Works" Method (Git Tag)
No manual downloads required. Install directly from our tagged releases using pip and git.

```bash
# Replace OWNER/REPO and v0.1.0 with your actual details
pip install "taskx @ git+ssh://git@github.com/OWNER/REPO.git@v0.1.0"
```

### The "Air-Gapped" Method (Wheel)
Ideal for secure environments or when GitHub access is restricted.

1. Download the latest `.whl` file from [GitHub Releases](https://github.com/OWNER/REPO/releases).
2. Install offline:
   ```bash
   pip install ./taskx-0.1.0-py3-none-any.whl
   ```

---

## 🛠 Project Integration

### Requirements File
Add this line to your `requirements.txt` to pin your project to a stable release:

```text
taskx @ git+ssh://git@github.com/OWNER/REPO.git@v0.1.0
```

Then install as usual:
```bash
pip install -r requirements.txt
```

### Pyproject.toml (Poetry / Hatch)
For modern Python projects using `pyproject.toml`:

**Hatch / Setuptools:**
```toml
[project.dependencies]
taskx = { git = "ssh://git@github.com/OWNER/REPO.git", tag = "v0.1.0" }
```

**Poetry:**
```toml
[tool.poetry.dependencies]
taskx = { git = "ssh://git@github.com/OWNER/REPO.git", tag = "v0.1.0" }
```

---

## 🔄 Upgrading

Keeping TaskX up to date is simple.

**From Git:**
```bash
pip install --upgrade "taskx @ git+ssh://git@github.com/OWNER/REPO.git@v0.2.0"
```

**From Wheel:**
```bash
pip install --upgrade ./taskx-0.2.0-py3-none-any.whl
```

### Verify Upgrade
After upgrading, run our built-in doctor to ensure everything is perfect.

```bash
taskx doctor
```
Checks:
- ✅ Imports
- ✅ Schema integrity
- ✅ Package health

---

## 📦 Unified Installer Script

For teams and automated environments, we provide a unified installer script (`scripts/install_taskx.sh`). This script ensures consistency across all your projects.

### Using `TASKX_VERSION.lock` (Recommended)
Place a `TASKX_VERSION.lock` file in your repository root to pin the version for everyone on the team.

**Example `TASKX_VERSION.lock`:**
```ini
version = 0.3.0
mode = git
owner = myorg
repo = taskx
```

**Install:**
```bash
bash scripts/install_taskx.sh
```

### Environment Variables
You can also drive the installer with environment variables (great for CI/CD).

```bash
export TASKX_OWNER=myorg
export TASKX_REPO=taskx
export TASKX_VERSION=0.3.0

bash scripts/install_taskx.sh
```

### Installer Modes
- **Auto:** Detects best method based on env vars.
- **Git:** Clones and installs specific tag/ref.
- **Packages:** Installs from GitHub Packages (requires token).
- **Local:** Installs in editable mode from a local path.

Use `--help` for full options:
```bash
bash scripts/install_taskx.sh --help
```
