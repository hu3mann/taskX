# CLAUDE.md — Evergreen Project Memory (Dopemux-Compatible)

Evergreen: DO NOT edit per task. Task packets change; this file stays stable.

## 0) Prime rule
TASK PACKETS ARE LAW.
If no task packet is provided: STOP and ask for it.

## 1) PLAN vs ACT mode (binding)
PLAN mode:
- Focus on architecture, tradeoffs, and clean breakdowns (max 3 options when needed).
- Use the Dopemux toolchain for design decisions; log decisions to ConPort.

ACT mode:
- Make minimal diffs that satisfy the task packet.
- Use codebase context tools before editing; run verification before claiming "done."

## 2) Attention-state adaptive output (binding defaults)
If unsure, assume "focused."
- scattered: concise, one next action
- focused: structured, up to 3 prioritized actions
- hyperfocus: comprehensive, full plan + deeper verification

(These defaults are consistent with your mode/attention routing docs.)

## 3) Quick Start Commands

### Development Setup
```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install git hooks
scripts/install-git-hooks.sh
```

### Build & Test
```bash
# Run tests with coverage (configured in pyproject.toml)
pytest

# Type checking
mypy src/

# Linting
ruff check .

# Format check
ruff format --check .

# Build distribution packages
python -m build
# or
scripts/taskx_build.sh
```

### TaskX CLI Usage
```bash
# Diagnostic health check
taskx doctor

# Basic task lifecycle
taskx compile-tasks --mode mvp --max-packets 5
taskx run-task --task-id T001
taskx gate-allowlist --run ./out/runs/RUN_..._T001
taskx promote-run --run ./out/runs/RUN_..._T001

# Dopemux namespace (auto-discovery)
taskx dopemux compile
taskx dopemux run --task-id T002
taskx dopemux gate
```

## 4) Project Structure

```
src/taskx/          # Core task packet engine
├── cli.py          # Main CLI entry point (Typer-based)
├── doctor.py       # Diagnostic tool implementation
├── ci_gate.py      # Allowlist gate checking
├── pipeline/       # Task compilation, execution, promotion
└── project/        # Project initialization and mode management

src/taskx_adapters/ # Dopemux integration
└── dopemux.py      # Auto-discovery of Dopemux paths

taskx_schemas/      # JSON schemas packaged with distribution
schemas/            # Schema definitions for validation

scripts/            # Build and installation automation
├── taskx_build.sh          # Build sdist + wheel
├── install-git-hooks.sh    # Install pre-commit hooks
└── taskx_install_into_repo.sh  # Install TaskX into other repos

docs/               # User documentation
├── INSTALL.md      # Installation guide
├── RELEASE.md      # Release process
└── PROJECT_DOCTOR.md  # Doctor tool documentation
```

## 5) Dopemux workflow defaults

RESEARCH:
- Use dope-context for in-repo code examples and patterns.

DESIGN:
- Log all meaningful decisions to ConPort with log_decision.

IMPLEMENTATION:
- Use serena-v2 + dope-context FIRST to locate code and patterns.
- Log progress to ConPort as work advances.

REVIEW / COMMIT:
- Run `pre-commit run --all-files` before commit.
- Update ConPort progress to DONE (or current status).

## 6) Coding + testing norms (repo-generic defaults)
- Match existing conventions first.
- New behavior must have tests (unit for logic; integration when behavior spans stages).
- Never claim tests passed unless you ran them; otherwise say "not run" and why.
- All functions must be typed (mypy --strict enforcement).

## 7) Key Files

- `pyproject.toml` - Project metadata, dependencies, tool configuration (Hatchling build, Ruff lint, pytest, mypy)
- `TASKX_VERSION.lock` - Version pinning for deterministic builds
- `.taskxroot` - Marks TaskX project root
- `taskx_bundle.yaml` - Task bundle configuration
- `README.md` - User-facing project overview and quick start

## 8) Development Gotchas

- **Deterministic time**: TaskX mocks `datetime.now()` for reproducible builds
- **Allowlist enforcement**: Gate rejects any file changes not in allowlist
- **Offline-first design**: All dependencies must be pre-installed; no network access during runs
- **Strict typing**: Project uses `mypy --strict` - all functions must be typed
- **Test coverage**: pytest configured to fail under 1% coverage (see pyproject.toml line 132)
- **Pre-commit required**: Changes must pass `pre-commit run --all-files` before commit
- **No `datetime.now()`**: Use `timestamp_mode="deterministic"` for release builds
- **Token-gated commits**: Cannot commit without a promotion token from gate-allowlist pass

## 9) New Command Surfaces

- `taskx project shell init|status`
- `taskx project upgrade`
- `taskx route init|plan|handoff|explain`
- `taskx pr open`

Branch restore contract:
- If a TaskX command switches branches, it must restore original branch/HEAD unless explicitly disabled.

## 10) Response format (mandatory)
A) MODE + attention state
B) PLAN
C) CHANGES
D) COMMANDS RUN + RESULTS
E) CONPORT LOGGING
F) NEXT ACTION or CHECKPOINT STOP

<!-- TASKX:AUTOGEN:START -->
<!-- (managed by taskx docs refresh-llm) -->
<!-- TASKX:AUTOGEN:END -->
