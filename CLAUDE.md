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

<!-- TASKX:BEGIN -->
<!-- directive-pack:taskx@v1 -->
## TaskX Directives (Base)

1. Task packets are law.
2. Perform only actions explicitly authorized by the active task packet.
3. Scope is strict: no drive-by refactors, no opportunistic cleanup, no hidden extra work.
4. Treat allowlists, file scopes, and verification gates as hard requirements.
5. Use evidence-first reasoning for every claim.
6. Never fabricate command runs, outputs, file states, tests, or approvals.
7. If evidence is missing, mark the claim `UNKNOWN` and define a deterministic check.
8. Verification is mandatory for completion.
9. Record verification with the exact commands run and raw outputs.
10. Do not summarize away failing output; include failure details and exit codes.
11. Deterministic operation is required:
12. Do not claim a command was run unless its output is present in logs.
13. Do not claim a file changed unless the diff reflects it.
14. Use minimal diffs and localized edits.
15. Keep behavior stable unless the packet explicitly authorizes a behavior change.
16. Keep assumptions explicit and testable.
17. Do not invent requirements, contracts, schemas, or policy text.
18. Respect stop conditions exactly as written in the packet.
19. Escalate immediately when blocked by missing artifacts, permissions, or contradictory instructions.
20. Escalation must include:
21. What is blocked.
22. Why it is blocked.
23. The smallest packet change needed to proceed.
24. Completion requires an Implementer Report with:
25. Summary of changes.
26. Files changed and added.
27. Verification commands and raw outputs.
28. Deviations from packet instructions (if any).
29. Explicit stop-condition confirmation.
30. If any required gate was not run, report incomplete and stop.
<!-- TASKX:END -->

<!-- CHATX:BEGIN -->
(disabled)
<!-- CHATX:END -->
