# MaidanPlay-June150

Rewrite of the legacy `june-one50` Google Sheets-backed SPA into a typed FastAPI + Next.js stack with proper auth, server-side permissions, and a Postgres source of truth.

## Stack
- **Backend** — FastAPI on `:8000`, Postgres via `psycopg` (Supabase in production). Email/password auth with scrypt hashing and HMAC-signed bearer tokens (`pf`-bound to the current password hash, so resets invalidate sessions instantly).
- **Frontend** — Next.js 16 (App Router) + React 19, single client component `OpsApp.tsx` driving a hash-routed SPA.

## Run locally

### Backend
The backend needs a Postgres database — set `DATABASE_URL` to your connection string (Supabase, local Postgres, etc.).
```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export DATABASE_URL='postgresql://user:pass@host:5432/postgres'
export JUNE_ONE50_SECRET='change-me'
.venv/bin/uvicorn app.main:app --reload --port 8000
```
On first run the database seeds itself with users (default password `MaidanPlay@2026`), batch config, and demo students.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000.

## Seed logins
Default password for all seeded users: **`MaidanPlay@2026`** (super-admin rotates per person via Admin Panel).

| Role | Sample email |
|---|---|
| Super-admin (admin) | `abhimanyu@maidanplay.com`, `ruchir@maidanplay.com` |
| Super-admin (akash) | `akash@maidanplay.com` |
| Director (amit) | `amit@maidanplay.com`, `yuvrajchawla@maidanplay.com` (Vasu) |
| P&L Head (kush) | `kush@maidanplay.com`, `mdathar@maidanplay.com` (Athar) |
| Coach | `adi@maidanplay.com`, `daksh@maidanplay.com`, `eeshan@maidanplay.com` |
| Employee | `sanjana@maidanplay.com`, `aryan@maidanplay.com`, `pranjal@maidanplay.com` |

## Environment
- `DATABASE_URL` — Postgres connection string. **Required.** TLS (`sslmode=require`) is added automatically if missing.
- `JUNE_ONE50_SECRET` — HMAC secret for bearer tokens. **Set this in production.**
- `JUNE_ONE50_CORS_ORIGINS` — comma-separated allowed origins (set to the frontend URL in production).
- `JUNE_ONE50_SEED_DEMO` — set `0` to skip demo students on first boot.
- `JUNE_ONE50_DB_POOL_MAX` — max Postgres connections in the pool (default `10`).

## Deploy

### Backend → Render
The repo ships a [`render.yaml`](./render.yaml) Blueprint. In Render, **New + → Blueprint**, point it at this repo, and it provisions a Python web service from `backend/`:
- **Build:** `pip install -r requirements.txt`
- **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check:** `/api/health`

Set these env vars in the Render dashboard:
- `DATABASE_URL` — your Supabase/Postgres string.
- `JUNE_ONE50_CORS_ORIGINS` — your Vercel frontend URL (e.g. `https://maidanplay.vercel.app`).
- `JUNE_ONE50_SECRET` — generated automatically by the Blueprint.

> Render's filesystem is ephemeral, which is why state lives in Postgres rather than a local file — no persistent disk is required.

### Frontend → Vercel
Import the repo into Vercel and set **Root Directory** to `frontend` (Vercel auto-detects Next.js). Add one env var:
- `NEXT_PUBLIC_API_BASE_URL` — your Render backend URL (e.g. `https://maidanplay-backend.onrender.com`).

After both are live, make sure the backend's `JUNE_ONE50_CORS_ORIGINS` includes the exact Vercel domain.

## Layout
```
backend/
  app/
    main.py        # routes
    logic.py       # business rules, permission checks, password hashing
    security.py    # token signing/verification (pf-bound)
    db.py          # schema, connection helpers
    models.py      # Pydantic request/response models
    config.py      # seed users, batches, field defs
  scripts/
    import_legacy_json.py
frontend/
  app/             # Next.js App Router entry
  components/
    OpsApp.tsx     # the entire client app
  lib/
    api.ts, types.ts
```
