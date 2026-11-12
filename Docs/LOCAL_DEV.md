# Windows Local Development Guide (Bootstrap)

- Status: bootstrap baseline (P1-01A). Commands target Windows + PowerShell.
- Scope note: this guide covers the frontend and the FastAPI app only. Docker/PostgreSQL setup is out of scope here and requires separate approval; `docker/compose.yaml` exists but has **not** been validated or run locally.

## Prerequisites (verified versions)

- Python 3.11 (baseline: 3.11.9)
- Node 24 (baseline: 24.21.0); engine requirements of the pinned tools: Vite 8.3.8 `^20.19.0 || >=22.12.0`, Vitest 5.1.0 `^22.12.0 || ^24.0.0 || >=26.0.0`
- Git 2.55+ on `feature/P1-01-bootstrap`
- No external API keys; no DB needed for the bootstrap test suite

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
```

Optional type check: `cd frontend; npx tsc --noEmit` (TypeScript 7.0.2).

## Notes & gotchas

- No PostgreSQL/PostGIS service is required by this bootstrap; the suite here is
  DB-free. DB-dependent integration tests do not exist yet and must not be
  reported as passing without a running DB.
- `docker/compose.yaml` + `docker\.env.example` are written but not validated:
  no Docker Desktop install, WSL change, image pull, or container run has been
  performed or is approved; image tag `postgis/postgis:17-3.7` is unverified.
- Secrets: keep real values out of Git; `.env`/`.env.*` are gitignored,
  `.env.example` files remain as templates (AGENTS.md §5.4).
- Line endings: repo has `core.autocrlf=true`; Git normalizes on commit and
  converts on checkout. If a toolchain ever needs LF-checkout, decide
  `core.eol`/`core.autocrlf` explicitly rather than mixing.
- Ports: backend 8000, Vite default 5173 — change if occupied.
- This document is a guide, not a claim that all steps were machine-verified
  in CI; remote CI runs only after push/pull (not approved yet).
