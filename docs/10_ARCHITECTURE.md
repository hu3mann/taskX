# Architecture

Audience: Contributors, Maintainers
Status: Normative
Tone: Deterministic. Unapologetic.

---

## 1. What TaskX Is

TaskX is a deterministic execution kernel.

It takes a structured packet and makes a decision.

That decision is binary:

- Plan and execute one path.
- Refuse with evidence.

There is no third state.
There is no "maybe."
There is no hidden recovery mode.

TaskX does not guess.
TaskX does not retry behind your back.
TaskX does not perform invisible magic.

If it did not write an artifact, it did not happen.

---

## 2. The Execution Spine

The lifecycle is simple, linear, and honest.

Packet
↓
Validation
↓
Planning
↓
RoutePlan OR Refusal
↓
Runner (auto) OR Handoff (manual)
↓
Artifacts
↓
Exit

No side doors.
No background threads.
No secret tunnels.

Every branch terminates in written evidence.

---

## 3. The Packet Is Law

The packet is the only input surface that matters.

It defines:

- What is being attempted
- In what mode
- In what order
- Under what policy

TaskX does not read intent from:
- Environment variables (unless declared)
- Git state (unless declared)
- Prior runs
- "Common sense"

If the packet does not say it, TaskX does not assume it.

Precision is power.

---

## 4. Validation: Fail Fast, Fail Clean

Validation is not polite.
Validation is protective.

If the packet is malformed or incomplete:

- Execution stops immediately.
- A structured refusal artifact is written.
- A stable exit code is returned.

No silent downgrades.
No partial execution.
No "best effort."

Refusal is controlled discipline, not failure.

---

## 5. Planning: One Path Only

The planner preserves order.
The planner selects exactly one runner.
The planner produces a deterministic route plan.

The planner does not execute code.
The planner does not improvise.

Given identical inputs, it must produce identical output.

If it does not, that is a defect.

---

## 6. Refusal Is a First-Class Outcome

Refusal is not embarrassment.
Refusal is integrity.

Refusal happens when:

- Policy is violated.
- A runner is unavailable.
- Required inputs are missing.
- Environment integrity fails.
- The packet asks for something unsafe.

Refusal produces:

- Deterministic reasoning.
- A structured artifact.
- A stable exit code.
- Zero side effects.

TaskX would rather refuse than lie.

---

## 7. The Runner Model

In `auto` mode:

- Exactly one runner executes.
- No parallelism.
- No fallback runner.
- No implicit retry.
- No cascading attempts.

In `manual` mode:

- No runner executes.
- Structured handoff content is emitted.
- Artifacts are still written.

One invocation.
One path.
One outcome.

---

## 8. Artifact Law

Artifacts are the truth.

Console output is theater.
Artifacts are reality.

Every run must:

- Canonicalize output.
- Hash deterministically.
- Write before exit.
- Preserve structure.

Artifacts are not logs.
Artifacts are evidence.

If artifacts are incomplete or inconsistent, the run is invalid.

---

## 9. Determinism Is Non-Negotiable

For identical:

- Packet
- Declared inputs
- TaskX version

Outputs must be byte-stable.

Allowed variability must be:

- Explicit.
- Documented.
- Recorded.

Implicit nondeterminism is a kernel violation.

Convenience never outranks determinism.

---

## 10. Boundaries: What TaskX Refuses to Be

TaskX does not:

- Schedule recurring jobs.
- Persist cross-run memory.
- Coordinate multiple packets.
- Orchestrate distributed state.
- Retry operations automatically.
- Perform undeclared network calls.
- Execute multiple runners.
- Mutate repositories implicitly.

Those are ecosystem concerns.

TaskX stays small.
Small stays sharp.

---

## 11. Kernel vs Ecosystem

TaskX is the execution spine.

Higher systems may:

- Generate packets.
- Maintain memory.
- Schedule execution.
- Aggregate results.
- Provide UX.
- Add orchestration.

TaskX remains:

- Stateless between runs.
- Deterministic per invocation.
- Artifact-driven.
- Refusal-first.
- Single-path.

If a feature requires ambiguity, it does not belong here.

---

## 12. Stability Model

TaskX follows Semantic Versioning.

- Patch: bug fixes only.
- Minor: additive, backward-compatible.
- Major: contract-breaking.

The public contract lives in:

`11_PUBLIC_CONTRACT.md`

If determinism changes, the version changes.

No silent contract drift.

---

## Final Principle

TaskX is not designed to be helpful.

It is designed to be correct.

And correctness is hotter than convenience.

