# GitHub Copilot Instructions for TaskX

## Project Overview

TaskX is a deterministic task-packet lifecycle engine designed for operator-grade environments. It's built around strict compliance, offline-first execution, and reproducible builds.

**Core Philosophy**: Deterministic, auditable, and uncompromising. TaskX assumes the internet is down, mocks system time for reproducibility, and enforces strict allowlists for all file changes.

## Tech Stack

- **Language**: Python 3.11+
- **CLI Framework**: Typer
- **Build System**: Hatchling
- **Testing**: pytest with coverage enforcement
- **Linting**: Ruff
- **Type Checking**: mypy with `--strict` mode
- **Pre-commit**: Enforced via git hooks

## Development Setup

### Installation
```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install git hooks
scripts/install-git-hooks.sh
```

### Common Commands
```bash
# Run tests with coverage
pytest

# Type checking (strict mode)
mypy src/

# Linting
ruff check .

# Format check
ruff format --check .

# Build distribution
python -m build
# or
scripts/taskx_build.sh

# Run pre-commit checks
pre-commit run --all-files
```

## Project Structure

```
src/taskx/          # Core task packet engine
├── cli.py          # Main CLI entry point (Typer-based)
├── doctor.py       # Diagnostic tool implementation
├── ci_gate.py      # Allowlist gate checking
├── pipeline/       # Task compilation, execution, promotion
└── project/        # Project initialization and mode management

src/taskx_adapters/ # Dopemux integration
taskx_schemas/      # JSON schemas packaged with distribution
schemas/            # Schema definitions for validation
scripts/            # Build and installation automation
docs/               # User documentation (numbered spine: 00_*, 01_*, etc.)
tests/              # Unit and integration tests
```

## Coding Conventions

### Python Style
- **Type Hints**: Required for all new or modified public functions (mypy --strict enforcement)
- **Function Design**: Prefer small, testable functions; minimize side-effects
- **Error Handling**: Never swallow exceptions; fail with actionable messages
- **String Formatting**: Use f-strings for string interpolation
- **Imports**: Follow standard library → third-party → local pattern

### Code Examples
```python
# Good: Typed function with clear error handling
def load_task_packet(path: Path) -> TaskPacket:
    """Load and validate a task packet from disk."""
    if not path.exists():
        raise FileNotFoundError(f"Task packet not found: {path}")
    
    with path.open() as f:
        data = json.load(f)
    
    return TaskPacket.from_dict(data)

# Good: Environment variable handling with defaults
neon_mode = os.getenv("TASKX_NEON", "0") == "1"

# Good: Boolean flags use "0" and "1" string comparisons
if os.getenv("TASKX_OFFLINE", "1") == "1":
    # offline mode
    pass
```

### Testing Practices
- All new behavior must have tests (unit for logic; integration for cross-component behavior)
- Use pytest fixtures for common setup
- Test coverage requirement: >90% (enforced in CI)
- CLI commands tested using `typer.testing.CliRunner`
- Assertions on exit codes and output content

```python
# Example CLI test pattern
from typer.testing import CliRunner

def test_doctor_command():
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 0
    assert "TaskX Doctor" in result.output
```

### Documentation Standards
- User-facing docs use numbered canonical spine under `docs/` (e.g., `00_OVERVIEW.md`, `01_INSTALL.md`)
- Legacy filenames should be short redirect stubs to numbered files
- Docstrings required for public APIs
- Use examples in docstrings where helpful

## Git Workflow

### Branching
- Feature branches for all changes
- Descriptive branch names (e.g., `feat/add-routing`, `fix/gate-validation`)

### Commits
- **Pre-commit required**: All changes must pass `pre-commit run --all-files` before commit
- Write clear, descriptive commit messages
- Reference issue numbers where applicable

### CI Requirements
- CI runs `ruff check src/taskx` and `mypy src/taskx`
- Type checking enforces `disallow_untyped_defs = true`
- All tests must pass
- Coverage must meet threshold

## Boundaries and Security

### What You MUST NOT Do
- **Never commit secrets**: No API keys, tokens, or credentials in code
- **Never bypass allowlists**: Respect TaskX's file change allowlist enforcement
- **Never use network calls during runs**: TaskX is offline-first by design
- **Never use `datetime.now()` directly**: Use deterministic time mocking for builds
- **Never modify production config without explicit approval**

### What You SHOULD Do
- **Sanitize logs**: Never leak sensitive content in logging
- **Use atomic writes**: Prefer temp file → rename pattern for I/O operations
- **Validate inputs**: All user inputs should be validated before processing
- **Handle errors gracefully**: Provide actionable error messages with conditional formatting (neon/non-neon modes)

### Security Examples
```python
# Good: Redact sensitive data before logging
def log_config(config: dict[str, Any]) -> None:
    safe_config = {k: "***" if "secret" in k.lower() else v 
                   for k, v in config.items()}
    logger.info(f"Config: {safe_config}")

# Good: Atomic file write
temp_path = target_path.with_suffix(".tmp")
temp_path.write_text(content)
temp_path.rename(target_path)

# Good: Conditional error formatting
if neon_mode:
    console.print(f"[red]Error:[/red] {error_msg}")
else:
    print(f"Error: {error_msg}")
```

## TaskX-Specific Patterns

### Entry Points API
- Use `entry_points(group="...")` directly (Python 3.11+)
- Avoid deprecated `.get()` method

### CLI Error Handling
- Wrap operations in try-except blocks
- Print user-friendly error messages before raising `typer.Exit`
- Support both neon and non-neon modes for formatting

### Bash Scripts
- Use `set -euo pipefail` for strict error handling
- Make scripts executable and add shebang

### Runner Adapters
- All runner adapters follow identical structure
- Methods: `prepare()`, `run()`, `normalize()`
- Helper: `_select_step()`

## Key Development Gotchas

1. **Deterministic Time**: TaskX mocks `datetime.now()` for reproducible builds
2. **Allowlist Enforcement**: Gate rejects any file changes not in allowlist
3. **Offline-First Design**: All dependencies must be pre-installed; no network access during runs
4. **Strict Typing**: Project uses `mypy --strict` - all functions must be typed
5. **Pre-commit Required**: Changes must pass `pre-commit run --all-files` before commit
6. **Token-gated commits**: Cannot commit without a promotion token from gate-allowlist pass

## When Working on TaskX

### Before You Start
1. Read the relevant documentation in `docs/`
2. Check `AGENTS.md` and `CLAUDE.md` for project-specific agent instructions
3. Run `taskx doctor` to verify your environment

### During Development
1. Write tests alongside code changes
2. Run focused tests frequently (`pytest tests/unit/specific_test.py`)
3. Check types with `mypy src/` before committing
4. Verify linting with `ruff check .`

### Before Committing
1. Run `pre-commit run --all-files`
2. Ensure all tests pass: `pytest`
3. Verify type checking: `mypy src/`
4. Check coverage is acceptable

### Common TaskX Commands
```bash
# Diagnostic health check
taskx doctor

# Basic task lifecycle
taskx compile-tasks --mode mvp --max-packets 5
taskx run-task --task-id T001
taskx gate-allowlist --run ./out/runs/RUN_..._T001
taskx promote-run --run ./out/runs/RUN_..._T001

# Dopemux namespace
taskx dopemux compile
taskx dopemux run --task-id T002
taskx dopemux gate

# Project management
taskx project init
taskx project status
taskx project upgrade

# Routing
taskx route init
taskx route plan
taskx route handoff
```

## Questions to Ask Before Coding

1. Does this change require tests? (Almost always yes)
2. Are there existing patterns I should follow?
3. Will this work offline without network access?
4. Does this maintain deterministic behavior?
5. Am I respecting the allowlist constraints?
6. Have I added type hints for new functions?
7. Does this introduce any security concerns?

## Getting Help

- Check `docs/` for detailed documentation
- Review `AGENTS.md` for contribution guidelines
- Run `taskx doctor` for environment diagnostics
- Look at existing code for patterns and examples
