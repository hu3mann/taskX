# Contract Claims Inventory

This inventory captures absolute/contractual claims from governance docs using deterministic keyword extraction and manual review for absolute language.

## Extraction Scope

Requested scope:

- `README.md`
- `docs/11_PUBLIC_CONTRACT.md`
- `docs/12_ROUTER.md`
- `docs/14_PROJECT_DOCTOR.md`
- `docs/00_OVERVIEW.md`
- `docs/KERNEL_PRINCIPLES.md` (missing at audit time)
- `docs/REFUSAL_PHILOSOPHY.md` (missing at audit time)
- `CONTRIBUTING.md` (missing at audit time)
- `SECURITY.md` (missing at audit time)

## Claims

| claim_id | doc_source | claim_text |
| --- | --- | --- |
| C-0001 | `README.md` (`#` heading) | "TaskX is a deterministic task-packet execution kernel that plans one path or refuses with evidence." |
| C-0002 | `README.md` (`## Guarantees`) | "Artifact-first: if it did not write an artifact, it did not happen." |
| C-0003 | `README.md` (`## Guarantees`) | "Refusal-first: invalid or unsafe inputs produce a structured refusal with a stable exit code." |
| C-0004 | `README.md` (`## Guarantees`) | "Deterministic: identical packet + declared inputs + TaskX version yields identical outputs." |
| C-0005 | `README.md` (`## Guarantees`) | "Single-path: no hidden retries, no fallback runners, no background execution." |
| C-0006 | `README.md` (`## Deterministic Task Execution`) | "one packet = one commit stack" |
| C-0007 | `README.md` (`## Deterministic Task Execution`) | "zero accidental commits on `main`" |
| C-0008 | `README.md` (`## Deterministic Task Execution`) | "manual commits can break determinism guarantees" |
| C-0009 | `README.md` (`## Kernel vs ecosystem`) | "TaskX (kernel) validates packets, plans deterministically, executes one path (or emits a manual handoff), and writes canonical artifacts." |
| C-0010 | `docs/00_OVERVIEW.md` (`artifact-first and refusal-first`) | "If it cannot proceed under declared policy, it refuses with evidence." |
| C-0011 | `docs/00_OVERVIEW.md` (`artifact-first and refusal-first`) | "If it did not write an artifact, it did not happen." |
| C-0012 | `docs/00_OVERVIEW.md` (`## Kernel vs ecosystem`) | "Executes exactly one selected path in `auto` mode (or emits a handoff in `manual` mode)." |
| C-0013 | `docs/00_OVERVIEW.md` (`## Kernel vs ecosystem`) | "Writes canonical artifacts before exit." |
| C-0014 | `docs/00_OVERVIEW.md` (`## Promises`) | "Deterministic planning and artifact writing for identical inputs and version." |
| C-0015 | `docs/00_OVERVIEW.md` (`## Promises`) | "Stable refusal semantics with evidence." |
| C-0016 | `docs/00_OVERVIEW.md` (`## Promises`) | "No hidden retries or fallback execution paths." |
| C-0017 | `docs/00_OVERVIEW.md` (`## Non-goals`) | "Implicit network access." |
| C-0018 | `docs/00_OVERVIEW.md` (`## Non-goals`) | "Cross-run mutable state." |
| C-0019 | `docs/11_PUBLIC_CONTRACT.md` (`## Outputs`) | "TaskX writes deterministic artifacts for a given invocation:" |
| C-0020 | `docs/11_PUBLIC_CONTRACT.md` (`## Outputs`) | "Console output is informational. Artifacts are the record." |
| C-0021 | `docs/11_PUBLIC_CONTRACT.md` (`## Determinism rules`) | "Outputs must be byte-stable unless explicitly documented otherwise." |
| C-0022 | `docs/11_PUBLIC_CONTRACT.md` (`## Exit codes`) | "`0`: success" |
| C-0023 | `docs/11_PUBLIC_CONTRACT.md` (`## Exit codes`) | "`2`: refusal (contractual non-execution)" |
| C-0024 | `docs/11_PUBLIC_CONTRACT.md` (`## Exit codes`) | "`1`: error (unexpected failure)" |
| C-0025 | `docs/11_PUBLIC_CONTRACT.md` (`## Non-goals`) | "Implicit retries and fallback runners" |
| C-0026 | `docs/11_PUBLIC_CONTRACT.md` (`## Non-goals`) | "Undeclared network access" |
| C-0027 | `docs/11_PUBLIC_CONTRACT.md` (`## Non-goals`) | "Cross-run mutable state" |
| C-0028 | `docs/12_ROUTER.md` (`#` heading) | "TaskX Router v1 selects runner/model pairs deterministically and writes route artifacts." |
| C-0029 | `docs/12_ROUTER.md` (`## Flow`) | "Plan steps (order-preserving)" |
| C-0030 | `docs/12_ROUTER.md` (`## Refusal conditions and artifacts`) | "Planner exits with code `2` when:" |
| C-0031 | `docs/12_ROUTER.md` (`## Refusal conditions and artifacts`) | "In refusal mode, plan artifacts are still written with:" |
| C-0032 | `docs/14_PROJECT_DOCTOR.md` (`#` section intro) | "The project doctor inspects a repository and reports integrity status. It does not mutate project state." |
| C-0033 | `docs/14_PROJECT_DOCTOR.md` (`## What doctor never does`) | "It never mutates packet execution behavior." |
| C-0034 | `docs/14_PROJECT_DOCTOR.md` (`## What doctor never does`) | "It never modifies repository files unless explicitly running a fix mode." |
| C-0035 | `docs/14_PROJECT_DOCTOR.md` (`## Operator prompt export policy (Policy A)`) | "This export does not affect packet routing or execution behavior." |

