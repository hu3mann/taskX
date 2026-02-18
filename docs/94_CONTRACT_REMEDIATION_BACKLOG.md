# Contract Remediation Backlog

This backlog converts all non-`PROVEN` claims from `docs/93_CONTRACT_AUDIT_REPORT.md` into actionable follow-up work.

| claim_id | current_status | risk | proposed_fix | verification_test | follow-up_TP_id |
| --- | --- | --- | --- | --- | --- |
| C-0002 | PARTIAL | MEDIUM | Add artifact-presence invariants for every contract-facing command family. | Add integration tests asserting artifacts exist for route/commit/project doctor/orchestrate success+refusal paths. | TP-REMEDIATE-CONTRACT-0004 |
| C-0003 | PARTIAL | MEDIUM | Standardize refusal schema + exit behavior across command families. | Add parametrized CLI tests asserting `exit=2` with refusal artifact for each refusal-capable command. | TP-REMEDIATE-CONTRACT-0004 |
| C-0005 | PARTIAL | MEDIUM | Define and enforce "no runner fallback/retry" policy with explicit exceptions. | Add tests that only one adapter `run()` is invoked and no alternate runner executes on failure. | TP-REMEDIATE-CONTRACT-0006 |
| C-0006 | PARTIAL | MEDIUM | Enforce packet-scoped commit path policy (COMMIT PLAN required for packet runs). | Add tests that `commit-run` refuses packet runs with COMMIT PLAN unless explicit override is set. | TP-REMEDIATE-CONTRACT-0007 |
| C-0007 | CONFLICT | HIGH | Add `main` branch refusal guard to `commit_run` (override flag optional). | Test: `commit_run` on `main` returns refusal unless `--allow-main` (or equivalent) is explicitly passed. | TP-REMEDIATE-CONTRACT-0001 |
| C-0008 | UNKNOWN | LOW | Convert advisory text into precise contractual language or remove from contract inventory. | Docs lint/test that all contract claims map to an executable predicate. | TP-REMEDIATE-CONTRACT-0008 |
| C-0009 | PARTIAL | MEDIUM | Strengthen packet validation from JSON-object check to schema validation. | Add tests for invalid/missing required packet fields causing structured refusal. | TP-REMEDIATE-CONTRACT-0009 |
| C-0011 | PARTIAL | MEDIUM | Add global artifact-first guard and conformance tests. | Contract conformance suite checks artifact write before terminal exits for target commands. | TP-REMEDIATE-CONTRACT-0004 |
| C-0016 | PARTIAL | MEDIUM | Eliminate ambiguous fallback terminology or scope it explicitly to non-execution parsing only. | Static check ensures no runner failover code path exists in kernel execution modules. | TP-REMEDIATE-CONTRACT-0006 |
| C-0017 | PARTIAL | MEDIUM | Add explicit network-deny guardrails for kernel execution surfaces. | Static scan + runtime monkeypatch test that outbound network APIs raise/refuse in kernel paths. | TP-REMEDIATE-CONTRACT-0005 |
| C-0018 | CONFLICT | HIGH | Clarify contract to "no hidden cross-run memory" or redesign persistence model. | Contract tests compare allowed persisted artifacts against declared allowlist of persistence classes. | TP-REMEDIATE-CONTRACT-0002 |
| C-0019 | PARTIAL | MEDIUM | Expand deterministic artifact coverage beyond router/orchestrator. | Add byte-stability regression tests for each artifact-producing command family. | TP-REMEDIATE-CONTRACT-0010 |
| C-0020 | PARTIAL | LOW | Clarify artifact-vs-stdout contract semantics for handoff flows. | Docs + tests confirm artifact canonicality while stdout remains auxiliary. | TP-REMEDIATE-CONTRACT-0011 |
| C-0021 | PARTIAL | MEDIUM | Expand byte-stability assertions to all contract-critical outputs. | Add snapshot/hash tests across route, orchestrate, and stateful audit outputs. | TP-REMEDIATE-CONTRACT-0010 |
| C-0022 | PARTIAL | LOW | Add explicit command-level exit-code conformance matrix. | Parametrized tests asserting success exits with `0` for contract-scoped commands. | TP-REMEDIATE-CONTRACT-0012 |
| C-0023 | PARTIAL | LOW | Add explicit refusal exit-code conformance matrix. | Parametrized tests asserting refusal exits with `2` and refusal artifacts where applicable. | TP-REMEDIATE-CONTRACT-0012 |
| C-0024 | PARTIAL | LOW | Add explicit error exit-code conformance matrix. | Parametrized tests asserting unexpected error exits with `1`. | TP-REMEDIATE-CONTRACT-0012 |
| C-0025 | PARTIAL | MEDIUM | Add explicit no-retry/no-fallback-runner assertions in orchestrator. | Unit test forces primary failure and verifies no alternate runner invocation occurs. | TP-REMEDIATE-CONTRACT-0006 |
| C-0026 | PARTIAL | MEDIUM | Formalize undeclared-network ban with enforcement hooks. | Add static/network runtime tests to fail CI if outbound network call sites are introduced in kernel modules. | TP-REMEDIATE-CONTRACT-0005 |
| C-0027 | CONFLICT | HIGH | Align contract wording with actual persisted state model or remove persistence from kernel. | Add compliance test that fails if persisted state exceeds documented contract scope. | TP-REMEDIATE-CONTRACT-0002 |
| C-0032 | CONFLICT | HIGH | Split project doctor check mode from write-report mode. | Test `taskx project doctor --path X` performs zero filesystem writes unless `--fix`/`--write-reports` is specified. | TP-REMEDIATE-CONTRACT-0003 |
| C-0033 | PARTIAL | MEDIUM | Prove doctor/check isolation from packet execution behavior via integration tests. | Run route/orchestrate before/after doctor check and assert identical outputs/hashes. | TP-REMEDIATE-CONTRACT-0013 |
| C-0034 | CONFLICT | HIGH | Gate report writes behind explicit flag or fix mode; update docs accordingly. | Test ensures no file mutations in default check mode. | TP-REMEDIATE-CONTRACT-0003 |
| C-0035 | PARTIAL | LOW | Add regression tests that ops export does not alter route/orchestrate artifacts. | Execute export, then route/orchestrate with fixed inputs and assert byte-identical outputs. | TP-REMEDIATE-CONTRACT-0013 |

