# CODEX.md — Execution Contract (Dopemux-Compatible)

Evergreen: DO NOT edit per task. Task packets change; this file stays stable.

## 0) Prime directive
TASK PACKETS ARE LAW.
Implement exactly what the active task packet requests. No scope expansion.
If no task packet: STOP and ask for it.

## 1) Preflight (every task, mandatory)
1) Determine MODE: PLAN or ACT.
2) Docs-first: pal apilookup for any library/API uncertainty (Context7 is retired).
3) Context-first: serena-v2 + dope-context before editing code.
4) Planning-first (if needed): task-orchestrator breakdown.
5) Decision logging: ConPort log_decision for meaningful choices.

## 2) Review + commit gates (mandatory)
- Before commit: pal codereviewer.
- If security-sensitive: pal secaudit before commit.
- Before commit: pre-commit run --all-files.

## 3) Verification discipline
- Run the task packet’s VERIFICATION commands exactly.
- If none are provided: propose the smallest reasonable repo-native set and run what you can.
- Never claim success without results.

## 4) Output adaptation (attention state)
- scattered → one clear next action, minimal output
- focused → structured, max 3 actions
- hyperfocus → comprehensive plan and deeper checks
(Default: focused)

## 5) Completion response format (mandatory)
A) MODE + attention state
B) PLAN
C) CHANGES (files)
D) COMMANDS RUN + RESULTS
E) CONPORT LOGGING (logged / should log)
F) NEXT ACTION or CHECKPOINT STOP

## 6) New Command Surfaces
- `taskx project shell init|status`
- `taskx project upgrade`
- `taskx route init|plan|handoff|explain`
- `taskx pr open`

Branch restore contract:
- If a TaskX command switches branches, it must restore original branch/HEAD unless explicitly disabled.
