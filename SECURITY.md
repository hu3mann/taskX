# Security Policy 🔐

TaskX is small, strict, and deterministic by design.

If you find a way to bypass validation, tamper with artifacts, or introduce nondeterminism, we want to know immediately.

---

## Supported Versions

We support the latest minor release only.

Older versions are not maintained.

---

## Reporting a Vulnerability

Please do not open public issues for security reports.

Send a private report with:

- TaskX version
- OS and Python version
- minimal reproduction steps
- a redacted packet (if applicable)
- relevant artifacts or logs (redacted)

We aim to respond within 72 hours.

We don't posture.
We reproduce.
We patch cleanly.

---

## What Counts as Security-Relevant

- validation bypass
- artifact tampering or suppression
- exit code manipulation
- hidden network calls
- determinism compromise
- runner substitution behind policy

If you can make TaskX behave unpredictably, you've found something worth reporting.
