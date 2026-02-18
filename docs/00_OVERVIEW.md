# Overview ⚙️🖤

TaskX is a deterministic execution kernel.

It consumes packets.
It produces plans or refusals.
It executes **one** path.
It writes artifacts **every** time. 🧾

No silent fallbacks.
No "cute" retries.
No mind-reading.

If it didn't leave evidence, it didn't happen. 😈

---

## Why It Exists 🔥

Most automation tools are chaos goblins in a trench coat:

- They retry and pretend it's resilience.
- They "try something else" and call it helpful.
- They mutate state and act surprised when trust evaporates.

TaskX does not do improv.

TaskX does **discipline**:
- clarity over convenience
- refusal over deception
- artifacts over vibes

---

## Kernel vs Ecosystem 💅

TaskX is the execution spine, not the whole creature.

TaskX does **NOT**:
- schedule recurring jobs
- persist cross-run memory
- orchestrate multiple packets
- execute multiple runners
- retry automatically
- perform undeclared network calls
- mutate your repo behind your back

If you want orchestration, build it **above** the kernel.
The kernel stays tight. Tight stays trustworthy. 🖤

---

## Quick Start (Dev) 🧠⚡

We use `uv` because we like things fast and controlled.

```bash
uv sync
uv run pytest
uv run taskx --help
```

Only uv workflows are supported in this repository.

---

## The Law (Public Contract) 📜

Your guarantees live here:
- `docs/11_PUBLIC_CONTRACT.md`

If behavior changes, the version changes.
No silent drift. No quiet power moves. 🧾
