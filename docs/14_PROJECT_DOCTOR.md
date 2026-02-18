# Project Doctor

Audience: Maintainers
Status: Diagnostic Control Layer

The Doctor does not comfort you.

The Doctor inspects.
The Doctor diagnoses.
The Doctor reports.

And if something is wrong, the Doctor does not whisper.

---

## What the Doctor Checks

- Instruction block integrity
- Duplicate operator markers
- Configuration drift
- Missing required files
- Structural contradictions

It does not "fix" silently.
It does not "helpfully correct."

It observes.
It reports.
It exits with intent.

---

## Exit Codes

- PASS -> 0
- WARN -> 0
- FAIL -> non-zero (stable, deterministic)

FAIL does not mean chaos.
FAIL means: "Not acceptable."

---

## Export Behavior

By default, the Doctor exports diagnostic artifacts.

Even on FAIL.

Why?
Because evidence matters.
Silence is not discipline.

If you disable export, you are opting out of receipts.

---

## What the Doctor Will Never Do

- modify packet execution behavior
- retry validation
- silently rewrite files
- mask conflicts
- introduce nondeterminism

The Doctor does not negotiate with entropy.

---

## Philosophy

The Doctor does not shame you.

But it will absolutely document your mistakes.
