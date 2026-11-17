# Windows Local Development Guide (Bootstrap)

- Status: bootstrap baseline (P1-01A). Commands target Windows + PowerShell.
- Scope note: this guide covers the frontend and the FastAPI app; the default test suite is DB-free. Local Docker/PostgreSQL dev setup proceeded separately under approval (P1-DB-01B/02/02B - see `Docs/HANDOFF.md`): `docker/compose.yaml`, container `4ddalla-db`, loopback `127.0.0.1:5432`, PostgreSQL 17.12 + PostGIS 3.7. Local development only - not a production deployment. Validation limits and re-check procedure: handoff sections G/J.

## Prerequisites (verified versions)

- Python 3.11 (baseline: 3.11.9)
- Node 24 (baseline: 24.21.0); engine requirements of the pinned tools: Vite 8.3.8 `^20.19.0 || >=22.12.0`, Vitest 5.1.0 `^22.12.0 || ^24.0.0 || >=26.0.0`
- Git 2.55+ (repo workflow: `main` = 승인된 안정 기준선, `develop` = 개발 - `AGENTS.md`)
- No external API keys; default test suite is DB-free; DB-dependent checks are explicit (see Verify below).

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # if blocked by ExecutionPolicy: use -ExecutionPolicy Bypass, or skip activation and use full paths
.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm install                          # generates package-lock.json
```

## Run

```powershell
# backend (from repo root)
.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
# -> GET http://127.0.0.1:8000/health  (expect {"status":"ok"})

# frontend (new terminal)
cd frontend
npm run dev                          # Vite dev server, default http://localhost:5173
```

## Verify

```powershell
.venv\Scripts\ruff.exe check .
.venv\Scripts\python.exe -m pytest
cd frontend
npm run test                         # Vitest
npm run build                        # Vite production build
# DB checks are explicit/opt-in - a skip is environment-driven, never "passed":
#   1) default run: .venv\Scripts\python.exe -m pytest        # DB-free (DB groups skip without env by design)
#   2) live dev DB: DATABASE_URL from local gitignored docker/.env (value never printed/committed)
#      -> .venv\Scripts\python.exe -m pytest tests/test_db_layer.py -v   # missing env / failed connect = not skipped - report as fail/incomplete
#   3) isolated migration round-trip (opt-in, DDALLA_TEST_ISOLATED_MIGRATION_DB): rerun 2) with the flag on
#      guard: loopback + 5432 + postgresql+psycopg + non-protected DB only; own scratch DB is created/dropped; downgrade base never against a general DB
# CI (.github/workflows/ci.yml) is unchanged - default run stays DB-free
```

Optional type check: `cd frontend; npx tsc --noEmit` (TypeScript 7.0.2).

## Notes & gotchas

- Default suite is DB-free; DB-dependent tests exist (P1-DB-02/02B, P1-DB-HARDEN-01) - see Verify. Environment-driven skips are not passes; missing env / failed connect must be reported, not skipped over.
- Docker/PostgreSQL local dev DB: built and validated locally under approval (2026-11-15/16, P1-DB-01B/02/02B - HANDOFF sections G/J): image tag exists; container `4ddalla-db` via Compose; loopback `127.0.0.1:5432`; PostgreSQL 17.12; PostGIS 3.7 (USE_GEOS/USE_PROJ/USE_STATS=1); named volume survives restart (data preserved). Local development only - not a production deployment. 2026-11-17: db `healthcheck` added; `docker compose config` parse verified (no interpolation; container runtime health behavior not re-verified).
- Secrets: keep real values out of Git; `.env`/`.env.*` are gitignored,
  `.env.example` files remain as templates (AGENTS.md §5.4).
- Line endings: repo has `core.autocrlf=true`; Git normalizes on commit and
  converts on checkout. If a toolchain ever needs LF-checkout, decide
  `core.eol`/`core.autocrlf` explicitly rather than mixing.
- Ports: backend 8000, Vite default 5173 — change if occupied.
- This document is a guide, not a claim that all steps were machine-verified
  in CI; remote CI runs only after push/pull (not approved yet).
