# TaskX is a deterministic task-packet execution kernel that plans one path or refuses with evidence.

## Guarantees

- Artifact-first: if it did not write an artifact, it did not happen.
- Refusal-first: invalid or unsafe inputs produce a structured refusal with a stable exit code.
- Deterministic: identical packet + declared inputs + TaskX version yields identical outputs.
- Single-path: no hidden retries, no fallback runners, no background execution.

## Install

uv (recommended):

```bash
uv tool install taskx
taskx --help
```

pip:

```bash
python -m pip install taskx
taskx --help
```

See `docs/01_INSTALL.md` for developer workflows and testing.

## 60-second example

```bash
taskx route init --repo-root .
cat > PACKET.md <<'EOF'
# Packet
ROUTER_HINTS:
  risk: low
EOF
taskx route plan --repo-root . --packet PACKET.md
ls -1 out/taskx_route/
```

Expected outputs:

- `out/taskx_route/ROUTE_PLAN.json`
- `out/taskx_route/ROUTE_PLAN.md`
- `out/taskx_route/HANDOFF.md` (for handoff flows)

## Docs

- Overview: `docs/00_OVERVIEW.md`
- Install: `docs/01_INSTALL.md`
- Quickstart: `docs/02_QUICKSTART.md`
- Architecture: `docs/10_ARCHITECTURE.md`
- Public contract: `docs/11_PUBLIC_CONTRACT.md`
- Router: `docs/12_ROUTER.md`
- Task packet format: `docs/13_TASK_PACKET_FORMAT.md`
- Project doctor: `docs/14_PROJECT_DOCTOR.md`
- Worktrees and commit sequencing (maintainers): `docs/20_WORKTREES_COMMIT_SEQUENCING.md`
- Case bundles (maintainers): `docs/21_CASE_BUNDLES.md`
- Release (maintainers): `docs/90_RELEASE.md`

## Kernel vs ecosystem

TaskX (kernel) validates packets, plans deterministically, executes one path (or emits a manual handoff), and writes canonical artifacts.

Everything else (scheduling, orchestration, memory, UX) belongs in the ecosystem above the kernel.

