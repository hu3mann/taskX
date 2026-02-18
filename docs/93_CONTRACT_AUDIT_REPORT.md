# Contract Audit Report

## Scope + inputs

Exact documents and artifacts in scope for this audit run:

- `README.md`
- `docs/00_OVERVIEW.md`
- `docs/11_PUBLIC_CONTRACT.md`
- `docs/12_ROUTER.md`
- `docs/14_PROJECT_DOCTOR.md`
- `docs/KERNEL_PRINCIPLES.md` (missing at audit time)
- `docs/REFUSAL_PHILOSOPHY.md` (missing at audit time)
- `CONTRIBUTING.md` (missing at audit time)
- `SECURITY.md` (missing at audit time)
- `docs/91_CONTRACT_AUDIT_SCHEMA.md`
- `docs/92_CONTRACT_CLAIMS_INVENTORY.md`

## Method

- Status rubric: `docs/91_CONTRACT_AUDIT_SCHEMA.md`.
- Evidence requirements: file/line, exact grep hit + snippet, or asserting test name.
- Each claim from `docs/92_CONTRACT_CLAIMS_INVENTORY.md` gets one status: `PROVEN`, `PARTIAL`, `UNKNOWN`, or `CONFLICT`.
- Code/test-first bias: implementation and tests were treated as authoritative over docs.

## Findings table

| claim_id | status | evidence_summary |
| --- | --- | --- |
| C-0001 | PROVEN | Kernel plans/refuses deterministically and writes refusal artifacts (`src/taskx/orchestrator/kernel.py:105`, `src/taskx/orchestrator/kernel.py:116`, `tests/unit/taskx/test_orchestrate_v0_invariants.py:70`). |
| C-0002 | PARTIAL | Artifact index/write path exists (`src/taskx/artifacts/writer.py:15`) but no global enforcement proving all commands are artifact-first. |
| C-0003 | PARTIAL | Route refusal exit/code+artifact behavior is tested (`src/taskx/cli.py:2197`, `tests/unit/taskx/test_router_refusal.py:16`), but not uniformly proven for every command surface. |
| C-0004 | PROVEN | Determinism asserted in router/orchestrator tests (`tests/unit/taskx/test_router_plan_determinism.py:15`, `tests/unit/taskx/test_orchestrate_v0_invariants.py:70`). |
| C-0005 | PARTIAL | Single-runner execution is enforced (`src/taskx/orchestrator/kernel.py:202`, `tests/unit/taskx/test_orchestrate_v0_invariants.py:98`) but fallback code paths still exist (`src/taskx/router/reporting.py:107`). |
| C-0006 | PARTIAL | `commit-sequence` creates per-step commits with allowlist checks (`src/taskx/git/worktree_ops.py:451`, `src/taskx/git/worktree_ops.py:519`), but one-packet/one-stack is not globally enforced. |
| C-0007 | CONFLICT | `commit_run` can commit on `main` (no branch guard in `src/taskx/git/commit_run.py:167`; verified run produced `branch= main`, `commit_created= True`). |
| C-0008 | UNKNOWN | Advisory claim about manual commits “can break” determinism is not directly asserted by code/tests as a contractual invariant. |
| C-0009 | PARTIAL | Deterministic planning + one selected runner + artifacts are present (`src/taskx/orchestrator/kernel.py:105`, `src/taskx/orchestrator/kernel.py:202`, `src/taskx/artifacts/writer.py:15`), but packet validation is minimal JSON object validation (`src/taskx/orchestrator/kernel.py:291`). |
| C-0010 | PROVEN | Declared-policy refusal path emits artifacts (`src/taskx/router/planner.py:87`, `src/taskx/cli.py:2197`, `tests/unit/taskx/test_route_plan_refusal_artifacts.py:77`). |
| C-0011 | PARTIAL | Artifact writing is robust in orchestrator/router (`src/taskx/artifacts/writer.py:15`, `src/taskx/cli.py:2188`), but no universal runtime guard enforces this phrase across all commands. |
| C-0012 | PROVEN | Auto mode executes one selected step (`src/taskx/orchestrator/kernel.py:202`, `src/taskx/orchestrator/kernel.py:251`) and manual emits handoff (`src/taskx/orchestrator/kernel.py:160`, `tests/unit/taskx/test_orchestrate_v0_invariants.py:248`). |
| C-0013 | PROVEN | Route plan writes artifacts before refusal exit (`src/taskx/cli.py:2188`, `src/taskx/cli.py:2191`, `src/taskx/cli.py:2202`). |
| C-0014 | PROVEN | Deterministic planning/artifact behavior covered by deterministic tests (`tests/unit/taskx/test_router_plan_determinism.py:15`, `tests/unit/taskx/test_route_router_v1_invariants.py:93`). |
| C-0015 | PROVEN | Stable refusal semantics and evidence fields are emitted/tested (`src/taskx/router/planner.py:156`, `tests/unit/taskx/test_route_plan_refusal_artifacts.py:48`). |
| C-0016 | PARTIAL | No retry loop in planner path (`src/taskx/router/planner.py:102`), but fallback semantics appear in codebase (`src/taskx/router/reporting.py:107`). |
| C-0017 | PARTIAL | No direct network-client imports were found (`rg -n "requests\\.|httpx\\.|urllib|socket|aiohttp|boto3|openai|anthropic|mistral|xai|curl|wget" -S src tests` -> no hits), but no hard runtime network-block guard exists. |
| C-0018 | CONFLICT | Kernel/ecosystem writes persistent state (`src/taskx/router/availability.py:96`, `src/taskx/router/availability.py:107`, `src/taskx/orchestrator/kernel.py:302`). |
| C-0019 | PARTIAL | Deterministic artifacts are implemented for router/orchestrator (`src/taskx/router/reporting.py:13`, `src/taskx/artifacts/canonical_json.py:13`), but not proven for every invocation surface. |
| C-0020 | PARTIAL | Artifacts are primary records (`src/taskx/artifacts/writer.py:49`) but CLI behavior can still rely on stdout for handoff display (`src/taskx/cli.py:2312`). |
| C-0021 | PARTIAL | Byte-stability proven for key flows (`tests/unit/taskx/test_router_plan_determinism.py:15`, `tests/unit/taskx/test_orchestrate_v0_invariants.py:70`) but not globally across entire CLI. |
| C-0022 | PARTIAL | Success path uses exit `0` on route/orchestrate (`src/taskx/cli.py:2320`) but the contract is broader than verified surfaces. |
| C-0023 | PARTIAL | Refusal uses exit `2` in route/orchestrate (`src/taskx/cli.py:2202`, `src/taskx/cli.py:2326`) with tests (`tests/unit/taskx/test_router_refusal.py:16`), but not exhaustively proven for all commands. |
| C-0024 | PARTIAL | Error paths use exit `1` in route/orchestrate (`src/taskx/cli.py:2180`, `src/taskx/cli.py:2329`) but contract-wide completeness is not proven. |
| C-0025 | PARTIAL | Retry/fallback runner behavior is mostly absent in planner execution, but fallback code exists (`src/taskx/router/reporting.py:107`) and no explicit global prohibition guard exists. |
| C-0026 | PARTIAL | Network-library grep found no direct client usage, but absence-only evidence is not equivalent to enforced prohibition. |
| C-0027 | CONFLICT | Persistent mutable state exists in `.taskx` and run artifacts (`src/taskx/router/availability.py:96`, `src/taskx/git/worktree_ops.py:545`, `src/taskx/artifacts/writer.py:24`). |
| C-0028 | PROVEN | Router planning/writing is deterministic by implementation and tests (`src/taskx/router/planner.py:75`, `src/taskx/cli.py:2169`, `tests/unit/taskx/test_route_router_v1_invariants.py:93`). |
| C-0029 | PROVEN | Step order is preserved through planning and asserted by tests (`src/taskx/router/planner.py:102`, `tests/unit/taskx/test_route_plan_refusal_artifacts.py:53`). |
| C-0030 | PROVEN | Planner refusal conditions map to exit `2` (`src/taskx/router/planner.py:133`, `src/taskx/cli.py:2197`, `tests/unit/taskx/test_route_plan_refusal_artifacts.py:41`). |
| C-0031 | PROVEN | Refusal mode still writes plan artifacts and refusal data (`src/taskx/cli.py:2188`, `tests/unit/taskx/test_route_plan_refusal_artifacts.py:88`). |
| C-0032 | CONFLICT | Project doctor command writes report files even in check mode (`src/taskx/cli.py:3588`, `src/taskx/project/doctor.py:164`). |
| C-0033 | PARTIAL | `check_project` is read-only (`src/taskx/project/doctor.py:25`) but adjacent doctor flows can mutate files (`src/taskx/project/doctor.py:116`). |
| C-0034 | CONFLICT | “Never modifies files unless fix mode” contradicted by unconditional report writes (`src/taskx/cli.py:3589`, `src/taskx/project/doctor.py:172`). |
| C-0035 | PARTIAL | No direct coupling from ops export to route planner was found, but no explicit guard/test proves complete isolation. |

## Per-claim detail sections

### C-0001
- claim_text: "TaskX is a deterministic task-packet execution kernel that plans one path or refuses with evidence."
- status: PROVEN
- evidence:
  - `src/taskx/orchestrator/kernel.py:105` builds route plan from packet.
  - `src/taskx/orchestrator/kernel.py:116` returns refusal with reasons/artifacts.
  - `tests/unit/taskx/test_orchestrate_v0_invariants.py:70` asserts byte-identical rerun refusal artifacts.
- notes: Evidence exists in both implementation and tests.
- risk: LOW
- next_action: None.

### C-0002
- claim_text: "Artifact-first: if it did not write an artifact, it did not happen."
- status: PARTIAL
- evidence:
  - `src/taskx/artifacts/writer.py:15` central artifact writer for orchestrator.
  - `tests/unit/taskx/test_orchestrate_v0_invariants.py:42` asserts artifact set and hash index.
- notes: Strong for orchestrator; not uniformly enforced for all CLI command families.
- risk: MEDIUM
- next_action: Add a kernel-wide invariant test matrix for artifact presence per public command family.

### C-0003
- claim_text: "Refusal-first: invalid or unsafe inputs produce a structured refusal with a stable exit code."
- status: PARTIAL
- evidence:
  - `src/taskx/cli.py:2197` route refusal exits with code 2 after writing artifacts.
  - `tests/unit/taskx/test_router_refusal.py:16` validates refusal contract.
- notes: Verified for router/orchestrator; not complete across all commands.
- risk: MEDIUM
- next_action: Add exit-code/refusal contract tests for remaining stateful commands.

### C-0004
- claim_text: "Deterministic: identical packet + declared inputs + TaskX version yields identical outputs."
- status: PROVEN
- evidence:
  - `tests/unit/taskx/test_router_plan_determinism.py:15` byte-identical route plan JSON.
  - `tests/unit/taskx/test_orchestrate_v0_invariants.py:70` byte-identical refusal artifacts across reruns.
- notes: Direct deterministic assertions exist.
- risk: LOW
- next_action: None.

### C-0005
- claim_text: "Single-path: no hidden retries, no fallback runners, no background execution."
- status: PARTIAL
- evidence:
  - `src/taskx/orchestrator/kernel.py:202` selects a single step for execution.
  - `tests/unit/taskx/test_orchestrate_v0_invariants.py:98` asserts only selected runner executes.
  - `src/taskx/router/reporting.py:107` contains a fallback path (legacy refusal format parsing).
- notes: Core execution path is single-runner; fallback semantics still exist in surrounding code.
- risk: MEDIUM
- next_action: Document permitted fallback classes and prohibit runner fallback explicitly in tests.

### C-0006
- claim_text: "one packet = one commit stack"
- status: PARTIAL
- evidence:
  - `src/taskx/git/worktree_ops.py:451` commit-sequence enforces COMMIT PLAN staging.
  - `src/taskx/git/worktree_ops.py:530` creates one commit per plan step.
- notes: True for `commit-sequence`; not a universal guard across all commit paths.
- risk: MEDIUM
- next_action: Add a policy check to reject `commit-run` when COMMIT PLAN exists unless explicitly overridden.

### C-0007
- claim_text: "zero accidental commits on `main`"
- status: CONFLICT
- evidence:
  - `src/taskx/git/worktree_ops.py:457` has a `main` branch refusal in `commit_sequence`.
  - `src/taskx/git/commit_run.py:167` captures branch but has no `main` refusal before commit.
  - Verification run output: `status= passed`, `branch= main`, `commit_created= True` (direct reproduction).
- notes: Safety is present in one commit path, absent in another.
- risk: HIGH
- next_action: Add branch guard to `commit_run` (with explicit override flag).

### C-0008
- claim_text: "manual commits can break determinism guarantees"
- status: UNKNOWN
- evidence:
  - Claim is advisory language; no direct invariant test asserts this exact condition.
- notes: Not directly mappable to enforceable predicate in current test suite.
- risk: LOW
- next_action: Convert advisory text into an explicit testable policy if intended as contract.

### C-0009
- claim_text: "TaskX (kernel) validates packets, plans deterministically, executes one path (or emits a manual handoff), and writes canonical artifacts."
- status: PARTIAL
- evidence:
  - `src/taskx/orchestrator/kernel.py:291` packet validation is JSON-object-level only.
  - `src/taskx/orchestrator/kernel.py:202` one selected step execution.
  - `src/taskx/artifacts/canonical_json.py:13` canonical JSON writing.
- notes: Mostly true; packet validation depth is limited.
- risk: MEDIUM
- next_action: Add schema-level packet validation in kernel entry path.

### C-0010
- claim_text: "If it cannot proceed under declared policy, it refuses with evidence."
- status: PROVEN
- evidence:
  - `src/taskx/router/planner.py:87` availability validation failure routes to refusal plan.
  - `src/taskx/cli.py:2197` refusal exits with code 2 after artifact write.
  - `tests/unit/taskx/test_route_plan_refusal_artifacts.py:77` confirms refusal artifacts exist.
- notes: Well covered.
- risk: LOW
- next_action: None.

### C-0011
- claim_text: "If it did not write an artifact, it did not happen."
- status: PARTIAL
- evidence:
  - `src/taskx/artifacts/writer.py:49` artifact index creation and hashes.
  - `tests/unit/taskx/test_orchestrate_v0_invariants.py:61` artifact index matches written files.
- notes: Strong orchestrator evidence; not globally asserted across all command groups.
- risk: MEDIUM
- next_action: Expand invariant tests beyond orchestrator/router commands.

### C-0012
- claim_text: "Executes exactly one selected path in `auto` mode (or emits a handoff in `manual` mode)."
- status: PROVEN
- evidence:
  - `src/taskx/orchestrator/kernel.py:202` selects single runnable step.
  - `src/taskx/orchestrator/kernel.py:160` manual mode emits handoff path.
  - `tests/unit/taskx/test_orchestrate_v0_invariants.py:248` validates manual handoff artifacts/chunks.
- notes: Directly enforced and tested.
- risk: LOW
- next_action: None.

### C-0013
- claim_text: "Writes canonical artifacts before exit."
- status: PROVEN
- evidence:
  - `src/taskx/cli.py:2188` writes JSON plan.
  - `src/taskx/cli.py:2191` writes markdown plan.
  - `src/taskx/cli.py:2202` then exits refusal path.
- notes: Ordering is explicit in route path.
- risk: LOW
- next_action: None.

### C-0014
- claim_text: "Deterministic planning and artifact writing for identical inputs and version."
- status: PROVEN
- evidence:
  - `tests/unit/taskx/test_router_plan_determinism.py:15`.
  - `tests/unit/taskx/test_route_router_v1_invariants.py:93`.
- notes: Explicit deterministic assertions exist.
- risk: LOW
- next_action: None.

### C-0015
- claim_text: "Stable refusal semantics with evidence."
- status: PROVEN
- evidence:
  - `src/taskx/router/planner.py:156` normalized refusal reason creation.
  - `tests/unit/taskx/test_route_plan_refusal_artifacts.py:48` refusal reason structure assertions.
- notes: Stable shape and behavior covered.
- risk: LOW
- next_action: None.

### C-0016
- claim_text: "No hidden retries or fallback execution paths."
- status: PARTIAL
- evidence:
  - `src/taskx/router/planner.py:102` no retry loop in step selection path.
  - `src/taskx/router/reporting.py:107` explicit fallback branch for legacy refusal format.
- notes: Retry is not evident in core planner, but fallback branches exist.
- risk: MEDIUM
- next_action: Define and enforce a precise "allowed fallback" policy.

### C-0017
- claim_text: "Implicit network access."
- status: PARTIAL
- evidence:
  - `rg -n "requests\\.|httpx\\.|urllib|socket|aiohttp|boto3|openai|anthropic|mistral|xai|curl|wget" -S src tests` returned no hits.
- notes: Negative grep evidence only; no hard enforcement guard.
- risk: MEDIUM
- next_action: Add explicit network-ban tests/guardrails for kernel command paths.

### C-0018
- claim_text: "Cross-run mutable state."
- status: CONFLICT
- evidence:
  - `src/taskx/router/availability.py:96` canonical `.taskx/runtime/availability.yaml` path.
  - `src/taskx/router/availability.py:107` writes availability YAML.
  - `src/taskx/orchestrator/kernel.py:302` deterministic persistent run directories under `out/runs`.
- notes: Persistent mutable state is part of current implementation.
- risk: HIGH
- next_action: Reword docs to "no hidden cross-run memory" or narrow scope to planner internals.

### C-0019
- claim_text: "TaskX writes deterministic artifacts for a given invocation:"
- status: PARTIAL
- evidence:
  - `src/taskx/router/reporting.py:13` deterministic route payload construction.
  - `src/taskx/artifacts/canonical_json.py:13` canonical serialization.
- notes: Strong in router/orchestrator, not fully established across all subsystems.
- risk: MEDIUM
- next_action: Add deterministic artifact checks for additional command families.

### C-0020
- claim_text: "Console output is informational. Artifacts are the record."
- status: PARTIAL
- evidence:
  - `src/taskx/artifacts/writer.py:49` artifact index as canonical record.
  - `src/taskx/cli.py:2312` orchestrate CLI still emits operational info via stdout.
- notes: Mostly consistent; wording may be too absolute given handoff stdout semantics.
- risk: LOW
- next_action: Clarify docs that artifacts are canonical while stdout may carry operator hints.

### C-0021
- claim_text: "Outputs must be byte-stable unless explicitly documented otherwise."
- status: PARTIAL
- evidence:
  - `tests/unit/taskx/test_router_plan_determinism.py:15` byte-identical route outputs.
  - `tests/unit/taskx/test_orchestrate_v0_invariants.py:70` byte-identical refusal artifacts.
- notes: Verified for core flows, not exhaustively for full CLI.
- risk: MEDIUM
- next_action: Extend byte-stability tests to additional artifact-producing commands.

### C-0022
- claim_text: "`0`: success"
- status: PARTIAL
- evidence:
  - `src/taskx/cli.py:2320` orchestrate success exit code 0.
- notes: Correct for audited path; not globally proven for all contract-relevant commands.
- risk: LOW
- next_action: Add a contract exit-code conformance test suite.

### C-0023
- claim_text: "`2`: refusal (contractual non-execution)"
- status: PARTIAL
- evidence:
  - `src/taskx/cli.py:2202` route refusal exit 2.
  - `src/taskx/cli.py:2326` orchestrate refusal exit 2.
  - `tests/unit/taskx/test_router_refusal.py:16` asserts route refusal behavior.
- notes: Strong for router/orchestrate; broader contract still partially covered.
- risk: LOW
- next_action: Add refusal exit-code checks for more commands.

### C-0024
- claim_text: "`1`: error (unexpected failure)"
- status: PARTIAL
- evidence:
  - `src/taskx/cli.py:2180` route plan generic error path exits 1.
  - `src/taskx/cli.py:2329` orchestrate error path exits 1.
- notes: Evidence exists but not comprehensive across all commands.
- risk: LOW
- next_action: Add global exit-code conformance tests.

### C-0025
- claim_text: "Implicit retries and fallback runners"
- status: PARTIAL
- evidence:
  - `src/taskx/orchestrator/kernel.py:225` only selected adapter is used.
  - `src/taskx/router/reporting.py:107` fallback branch exists (legacy refusal parsing).
- notes: Execution path has no retry/failover runner loop, but fallback terminology exists in code.
- risk: MEDIUM
- next_action: Add explicit no-runner-failover assertion tests in orchestrator.

### C-0026
- claim_text: "Undeclared network access"
- status: PARTIAL
- evidence:
  - `rg -n "requests\\.|httpx\\.|urllib|socket|aiohttp|boto3|openai|anthropic|mistral|xai|curl|wget" -S src tests` returned no hits.
- notes: Absence-based signal only.
- risk: MEDIUM
- next_action: Add static and runtime network-deny checks for kernel commands.

### C-0027
- claim_text: "Cross-run mutable state"
- status: CONFLICT
- evidence:
  - `src/taskx/router/availability.py:96` / `src/taskx/router/availability.py:107` persistent runtime config.
  - `src/taskx/git/worktree_ops.py:545` writes `COMMIT_SEQUENCE_RUN.json`.
  - `src/taskx/artifacts/writer.py:24` writes persistent run artifacts.
- notes: Implementation explicitly persists mutable run/project state.
- risk: HIGH
- next_action: Narrow contract wording or redesign persistence model.

### C-0028
- claim_text: "TaskX Router v1 selects runner/model pairs deterministically and writes route artifacts."
- status: PROVEN
- evidence:
  - `src/taskx/router/planner.py:75` deterministic planner.
  - `src/taskx/cli.py:2169` route plan command writes artifacts.
  - `tests/unit/taskx/test_route_router_v1_invariants.py:93` determinism/refusal artifact assertions.
- notes: Strong implementation + test proof.
- risk: LOW
- next_action: None.

### C-0029
- claim_text: "Plan steps (order-preserving)"
- status: PROVEN
- evidence:
  - `src/taskx/router/planner.py:102` iterates `planned_steps` in declared order.
  - `tests/unit/taskx/test_route_plan_refusal_artifacts.py:53` asserts ordered steps.
- notes: Explicitly enforced.
- risk: LOW
- next_action: None.

### C-0030
- claim_text: "Planner exits with code `2` when:"
- status: PROVEN
- evidence:
  - `src/taskx/router/planner.py:133` threshold refusal reason generation.
  - `src/taskx/cli.py:2197` refusal status triggers exit 2.
  - `tests/unit/taskx/test_route_plan_refusal_artifacts.py:41` and `:88` assert refusal code/path.
- notes: Direct proof.
- risk: LOW
- next_action: None.

### C-0031
- claim_text: "In refusal mode, plan artifacts are still written with:"
- status: PROVEN
- evidence:
  - `src/taskx/cli.py:2188` / `src/taskx/cli.py:2191` writes JSON + markdown before refusal exit.
  - `tests/unit/taskx/test_route_plan_refusal_artifacts.py:88` asserts artifact existence.
- notes: Confirmed.
- risk: LOW
- next_action: None.

### C-0032
- claim_text: "The project doctor inspects a repository and reports integrity status. It does not mutate project state."
- status: CONFLICT
- evidence:
  - `src/taskx/cli.py:3588` runs `check_project` in non-fix mode.
  - `src/taskx/cli.py:3589` still writes reports.
  - `src/taskx/project/doctor.py:172` / `:173` write markdown/json files.
- notes: Inspection mode still mutates `generated/` outputs.
- risk: HIGH
- next_action: Separate pure-check mode from report-writing side effects, or adjust docs.

### C-0033
- claim_text: "It never mutates packet execution behavior."
- status: PARTIAL
- evidence:
  - `src/taskx/project/doctor.py:25` check path analyzes files and returns report only.
  - `src/taskx/project/doctor.py:116` fix path mutates instruction files/mode/prompt files.
- notes: No direct packet execution mutation observed, but claim scope is broad and not formally tested.
- risk: MEDIUM
- next_action: Add an integration test proving doctor/check operations do not alter route/orchestrate outputs.

### C-0034
- claim_text: "It never modifies repository files unless explicitly running a fix mode."
- status: CONFLICT
- evidence:
  - `src/taskx/cli.py:3589` always calls `write_doctor_reports`.
  - `src/taskx/project/doctor.py:164` defines persistent report writer.
  - `src/taskx/project/doctor.py:172` / `:173` write files regardless of fix flag.
- notes: This is a direct contradiction.
- risk: HIGH
- next_action: Gate report writing behind `--fix` or add explicit `--write-reports` flag and revise docs.

### C-0035
- claim_text: "This export does not affect packet routing or execution behavior."
- status: PARTIAL
- evidence:
  - Router planner consumes `.taskx/runtime/availability.yaml` and packet hints (`src/taskx/router/planner.py:85`, `src/taskx/router/planner.py:98`).
  - Ops export/doctor paths are separate modules (`src/taskx/ops/cli.py`, audited) with no direct calls from router planner.
- notes: No direct coupling found, but explicit isolation test is missing.
- risk: LOW
- next_action: Add regression test: run route/orchestrate before/after ops export and assert identical artifacts.

## Risk summary

- Highest-risk `CONFLICT` claims: `C-0007`, `C-0018`, `C-0027`, `C-0032`, `C-0034`.
- Main drift pattern: docs use absolute language where code is either partial-coverage (`PARTIAL`) or explicitly contradictory (`CONFLICT`).
- Missing-scope risk: requested docs `docs/KERNEL_PRINCIPLES.md`, `docs/REFUSAL_PHILOSOPHY.md`, `CONTRIBUTING.md`, and `SECURITY.md` were absent in this branch, so claims from those sources could not be inventoried.

## Recommended remediation TPs

- TP-REMEDIATE-CONTRACT-0001: add branch-guard enforcement to `commit_run` (block `main` by default).
- TP-REMEDIATE-CONTRACT-0002: resolve cross-run-state contract wording vs implementation (narrow contract or redesign persistence model).
- TP-REMEDIATE-CONTRACT-0003: split project doctor check mode from report-writing side effects.
- TP-REMEDIATE-CONTRACT-0004: add explicit contract conformance tests for global exit codes and artifact-first behavior across command families.
- TP-REMEDIATE-CONTRACT-0005: add network-deny invariant checks (static + runtime) for kernel paths.
