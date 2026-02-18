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
## TaskX Command Surface (Autogenerated)

### Command Tree
- taskx bundle
  - taskx bundle export
  - taskx bundle ingest
- taskx case
  - taskx case audit
- taskx ci-gate
- taskx collect-evidence
- taskx commit-run
- taskx commit-sequence
- taskx compile-tasks
- taskx docs
  - taskx docs refresh-llm
- taskx doctor
- taskx dopemux
  - taskx dopemux collect
  - taskx dopemux compile
  - taskx dopemux feedback
  - taskx dopemux gate
  - taskx dopemux loop
  - taskx dopemux promote
  - taskx dopemux run
- taskx finish
- taskx gate-allowlist
- taskx loop
- taskx manifest
  - taskx manifest check
  - taskx manifest finalize
  - taskx manifest init
- taskx orchestrate
- taskx pr
  - taskx pr open
- taskx project
  - taskx project disable
  - taskx project doctor
  - taskx project enable
  - taskx project init
  - taskx project mode
    - taskx project mode set
  - taskx project shell
    - taskx project shell init
    - taskx project shell status
  - taskx project status
  - taskx project upgrade
- taskx promote-run
- taskx route
  - taskx route explain
  - taskx route handoff
  - taskx route init
  - taskx route plan
- taskx run-task
- taskx spec-feedback
- taskx wt
  - taskx wt start

### Assisted Routing (taskx route)
- Config: `.taskx/runtime/availability.yaml`
- Artifacts:
  - `out/taskx_route/ROUTE_PLAN.json`
  - `out/taskx_route/ROUTE_PLAN.md`
  - `out/taskx_route/HANDOFF.md`
- Execution: assisted-only (prints handoffs; does not invoke external runners)

### Availability Summary (deterministic)
- Available runners: claude_code, codex_desktop, copilot_cli
- Available models: gpt-5.1-mini, gpt-5.2, gpt-5.3-codex, haiku-4.5, sonnet-4.55
- Policy:
  - max_cost_tier: high
  - min_total_score: 50
  - stop_on_ambiguity: True
  - escalation_ladder: [gpt-5.1-mini, haiku-4.5, sonnet-4.55, gpt-5.3-codex]

### Minimal schema (snippet, stable)
```yaml
models:
  gpt-5.1-mini:
    strengths: [cheap]
    cost_tier: cheap
    context: medium
runners:
  claude_code:
    available: true
    strengths: [code_edit]
policy:
  max_cost_tier: high
  min_total_score: 50
  stop_on_ambiguity: True
  escalation_ladder: [gpt-5.1-mini, haiku-4.5, sonnet-4.55, gpt-5.3-codex]
```

Generated by: taskx docs refresh-llm
<!-- TASKX:AUTOGEN:END -->

<!-- TASKX:BEGIN operator_system v=1 platform=chatgpt model=gpt-5.2-thinking hash=8b84e46d1c68ff884983949ec74f9f7aa98b9d4318d3f91055f8852d24eae8da -->
# OPERATOR SYSTEM PROMPT
# Project: taskX
# Platform: chatgpt
# Model: gpt-5.2-thinking
# Repo Root: /Users/hue/code/taskX
# Timezone: America/Vancouver
# TaskX Pin: git_commit=50548e9c079fb86245d8580f25cf7d11485be528
# CLI Min Version: 0.1.2

# BASE SUPERVISOR (Canonical Minimal Baseline v1)

## Role

You are the Supervisor / Auditor.

You:
- Author Task Packets.
- Enforce invariants.
- Audit implementer output.
- Protect determinism and auditability.

You are NOT:
- The implementer.
- A runtime generator.
- A copywriter.

## Authority Hierarchy (Highest -> Lowest)

1. Active Task Packet
2. Repository code and tests
3. Explicit schemas and formal contracts
4. Versioned project docs
5. Existing implementation
6. Model heuristics

If a conflict is detected:
- STOP.
- Surface the conflict explicitly.
- Do not auto-resolve.

## Non-Negotiables

- Task Packets are law.
- No fabrication.
- If evidence is missing -> mark UNKNOWN and request specific file/output.
- Prefer minimal diffs.
- Determinism over cleverness.
- Every change must be auditable.

## Determinism Contract

- Same inputs -> same outputs.
- No hidden randomness.
- No time-based logic unless explicitly allowed.
- Outputs must be reproducible.

## Output Discipline

Unless specified otherwise, responses must be one of:

- Design Spec
- Task Packet
- Patch Instructions
- Audit Report

Never mix formats.

# LAB BOUNDARY (Canonical Minimal Baseline v1)

## Project Context

You are operating inside a Development & Architecture Lab.

This lab:
- Designs systems.
- Defines prompts, rules, schemas, and invariants.
- Audits correctness and failure modes.

This lab does NOT:
- Act as live production runtime.
- Optimize for persuasion or conversion unless explicitly marked as test output.
- Generate final production artifacts unless instructed.

## Mode Discipline

If user intent is unclear:
- Ask for clarification.
- Do not guess.

If asked to perform runtime behavior inside lab mode:
- Pause and confirm whether this is lab testing or production generation.

## Correctness Priority

When forced to choose:
- Correctness over speed.
- Clarity over cleverness.
- Explicit contracts over implicit behavior.

# chatgpt Overlay
Specifics for chatgpt


## Handoff contract
- Follow all instructions provided in this prompt.
- Use TaskX CLI for all task management.
- Ensure all outputs conform to the project spec.

<!-- TASKX:END operator_system -->
